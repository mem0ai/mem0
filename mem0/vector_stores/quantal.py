import json
import logging
import os
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    from quantal import Index
except ImportError:
    raise ImportError("Could not import quantal python package. Please install it with `pip install quantaldb`.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # similarity score (cosine)
    payload: Optional[Dict]  # metadata


class Quantal(VectorStoreBase):
    """quantal is an embedded vector index (no server): graph-routed search
    over quantized codes. Vectors are stored normalized and scored by inner
    product, i.e. cosine similarity. Deletes are O(1) tombstones, so no
    index rebuild is needed."""

    def __init__(
        self,
        collection_name: str,
        path: Optional[str] = None,
        embedding_model_dims: int = 1536,
    ):
        """
        Initialize the quantal vector store.

        Args:
            collection_name (str): Name of the collection.
            path (str, optional): Directory for the index and metadata files.
                Defaults to /tmp/quantal/<collection_name>.
            embedding_model_dims (int, optional): Dimension of the embedding
                vector. Defaults to 1536.
        """
        self.collection_name = collection_name
        self.path = path or f"/tmp/quantal/{collection_name}"
        self.embedding_model_dims = embedding_model_dims

        self.index = None
        self.docstore = {}  # memory id (str) -> payload dict
        self.id_map = {}  # memory id (str) -> internal id (int)
        self.rev_map = {}  # internal id (int) -> memory id (str)
        self.next_id = 0

        os.makedirs(self.path, exist_ok=True)
        index_path = f"{self.path}/{collection_name}.tq"
        meta_path = f"{self.path}/{collection_name}.json"
        if os.path.exists(index_path) and os.path.exists(meta_path):
            self._load(index_path, meta_path)
        else:
            self.create_col(collection_name)

    def _load(self, index_path: str, meta_path: str):
        try:
            self.index = Index.load(index_path)
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self.docstore = meta.get("docstore", {})
            self.id_map = {k: int(v) for k, v in meta.get("id_map", {}).items()}
            self.rev_map = {v: k for k, v in self.id_map.items()}
            self.next_id = int(meta.get("next_id", 0))
            logger.info(f"Loaded quantal index from {index_path} with {len(self.index)} vectors")
        except Exception as e:
            logger.warning(f"Failed to load quantal index: {e}")
            self.docstore, self.id_map, self.rev_map, self.next_id = {}, {}, {}, 0
            self.create_col(self.collection_name)

    def _save(self):
        if not self.path or self.index is None:
            return
        try:
            os.makedirs(self.path, exist_ok=True)
            self.index.save(f"{self.path}/{self.collection_name}.tq")
            meta = {
                "docstore": self.docstore,
                "id_map": self.id_map,
                "next_id": self.next_id,
            }
            with open(f"{self.path}/{self.collection_name}.json", "w", encoding="utf-8") as f:
                json.dump(meta, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save quantal index: {e}")

    def _normalize(self, vectors) -> np.ndarray:
        vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        if vectors.ndim == 1:
            vectors = vectors.reshape(1, -1)
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        return vectors / np.maximum(norms, 1e-30)

    def _to_output(self, hits) -> List[OutputData]:
        results = []
        for internal_id, score in hits:
            memory_id = self.rev_map.get(int(internal_id))
            if memory_id is None:
                continue
            payload = self.docstore.get(memory_id)
            if payload is None:
                continue
            results.append(OutputData(id=memory_id, score=float(score), payload=payload.copy()))
        return results

    def _apply_filters(self, payload: Dict, filters: Dict) -> bool:
        if not filters or not payload:
            return True
        for key, value in filters.items():
            if key not in payload:
                return False
            if isinstance(value, list):
                if payload[key] not in value:
                    return False
            elif payload[key] != value:
                return False
        return True

    def create_col(self, name: str, distance: str = None):
        """
        Create a new collection. quantal scores normalized vectors by inner
        product, so the distance is always cosine; `distance` is accepted
        for API compatibility and ignored.

        Args:
            name (str): Name of the collection.
            distance (str, optional): Ignored (always cosine).

        Returns:
            self: The Quantal instance.
        """
        self.index = Index(dim=self.embedding_model_dims)
        self.collection_name = name
        self._save()
        return self

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[list]): List of vectors to insert.
            payloads (Optional[List[Dict]], optional): List of payloads corresponding to vectors.
            ids (Optional[List[str]], optional): List of IDs corresponding to vectors.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]
        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length")

        internal_ids = np.arange(self.next_id, self.next_id + len(vectors), dtype=np.uint64)
        self.index.add(self._normalize(vectors), ids=internal_ids)
        for internal_id, memory_id, payload in zip(internal_ids, ids, payloads):
            self.docstore[memory_id] = payload.copy()
            self.id_map[memory_id] = int(internal_id)
            self.rev_map[int(internal_id)] = memory_id
        self.next_id += len(vectors)

        self._save()
        logger.info(f"Inserted {len(vectors)} vectors into collection {self.collection_name}")

    def search(
        self, query: str, vectors: List[list], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors. With filters, the search is restricted
        to the matching ids up front (exact scoring over the allowlist)
        rather than over-fetching and post-filtering.

        Args:
            query (str): Query (not used, kept for API compatibility).
            vectors (List[list]): Query vector.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (Optional[Dict], optional): Payload filters. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")
        if len(self.docstore) == 0:
            return []

        query_vector = self._normalize(vectors)

        if filters:
            allowlist = [
                self.id_map[memory_id]
                for memory_id, payload in self.docstore.items()
                if memory_id in self.id_map and self._apply_filters(payload, filters)
            ]
            if not allowlist:
                return []
            hits = self.index.search_filtered(query_vector, allowlist, k=top_k)
        else:
            hits = self.index.search(query_vector, k=top_k)

        return self._to_output(hits)

    def delete(self, vector_id: str):
        """
        Delete a vector by ID. quantal removes by tombstone in O(1); the
        index is not rebuilt.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        internal_id = self.id_map.pop(vector_id, None)
        if internal_id is None:
            logger.warning(f"Vector {vector_id} not found in collection {self.collection_name}")
            return

        self.index.remove(internal_id)
        self.rev_map.pop(internal_id, None)
        self.docstore.pop(vector_id, None)
        self._save()
        logger.info(f"Deleted vector {vector_id} from collection {self.collection_name}")

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and/or its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (Optional[List[float]], optional): Updated vector.
            payload (Optional[Dict], optional): Updated payload.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")
        if vector_id not in self.docstore:
            raise ValueError(f"Vector {vector_id} not found")

        if payload is not None:
            self.docstore[vector_id] = payload.copy()

        if vector is not None:
            old_internal = self.id_map[vector_id]
            self.index.remove(old_internal)
            self.rev_map.pop(old_internal, None)
            new_internal = self.next_id
            self.next_id += 1
            self.index.add(self._normalize([vector]), ids=np.array([new_internal], dtype=np.uint64))
            self.id_map[vector_id] = new_internal
            self.rev_map[new_internal] = vector_id

        self._save()
        logger.info(f"Updated vector {vector_id} in collection {self.collection_name}")

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector's payload by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector, or None if not found.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")
        if vector_id not in self.docstore:
            return None
        return OutputData(id=vector_id, score=None, payload=self.docstore[vector_id].copy())

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        if not self.path:
            return [self.collection_name] if self.index else []
        try:
            return [file.stem for file in Path(self.path).glob("*.tq")]
        except Exception as e:
            logger.warning(f"Failed to list collections: {e}")
            return [self.collection_name] if self.index else []

    def delete_col(self):
        """Delete the collection's files and reset in-memory state."""
        if self.path:
            try:
                for suffix in (".tq", ".json"):
                    file_path = f"{self.path}/{self.collection_name}{suffix}"
                    if os.path.exists(file_path):
                        os.remove(file_path)
                logger.info(f"Deleted collection {self.collection_name}")
            except Exception as e:
                logger.warning(f"Failed to delete collection: {e}")

        if self.index is not None:
            self.index.close()
        self.index = None
        self.docstore = {}
        self.id_map = {}
        self.rev_map = {}
        self.next_id = 0

    def col_info(self) -> Dict:
        """
        Get information about the collection.

        Returns:
            Dict: Collection information.
        """
        if self.index is None:
            return {"name": self.collection_name, "count": 0}
        return {
            "name": self.collection_name,
            "count": len(self.index),
            "dimension": self.index.dim,
            "distance": "cosine",
            "memory_bytes": self.index.memory_bytes,
        }

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[OutputData]:
        """
        List vectors in the collection.

        Args:
            filters (Optional[Dict], optional): Payload filters.
            top_k (int, optional): Maximum number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        if self.index is None:
            return []

        results = []
        for memory_id, payload in self.docstore.items():
            if filters and not self._apply_filters(payload, filters):
                continue
            results.append(OutputData(id=memory_id, score=None, payload=payload.copy()))
            if len(results) >= top_k:
                break
        return [results]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name)
