import logging
import os
import pickle
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel

import warnings

try:
    # Suppress SWIG deprecation warnings from FAISS
    warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*SwigPy.*")
    warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*swigvarlink.*")
    
    logging.getLogger("faiss").setLevel(logging.WARNING)
    logging.getLogger("faiss.loader").setLevel(logging.WARNING)

    import faiss
except ImportError:
    raise ImportError(
        "Could not import faiss python package. "
        "Please install it with `pip install faiss-gpu` (for CUDA supported GPU) "
        "or `pip install faiss-cpu` (depending on Python version)."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]  # memory id
    score: Optional[float]  # distance
    payload: Optional[Dict]  # metadata


class FAISS(VectorStoreBase):
    def __init__(
        self,
        collection_name: str,
        path: Optional[str] = None,
        distance_strategy: str = "euclidean",
        normalize_L2: bool = False,
        embedding_model_dims: int = 1536,
    ):
        """
        Initialize the FAISS vector store.

        Args:
            collection_name (str): Name of the collection.
            path (str, optional): Path for local FAISS database. Defaults to None.
            distance_strategy (str, optional): Distance strategy to use. Options: 'euclidean', 'inner_product', 'cosine'.
                Defaults to "euclidean".
            normalize_L2 (bool, optional): Whether to normalize L2 vectors. Only applicable for euclidean distance.
                Defaults to False.
        """
        self.collection_name = collection_name
        self.path = path or f"/tmp/faiss/{collection_name}"
        self.distance_strategy = distance_strategy
        self.normalize_L2 = normalize_L2
        self.embedding_model_dims = embedding_model_dims

        # Initialize storage structures
        self.index = None
        self.docstore = {}
        self.index_to_id = {}

        # Create directory if it doesn't exist
        if self.path:
            os.makedirs(os.path.dirname(self.path), exist_ok=True)

            # Try to load existing index if available
            index_path = f"{self.path}/{collection_name}.faiss"
            docstore_path = f"{self.path}/{collection_name}.pkl"
            if os.path.exists(index_path) and os.path.exists(docstore_path):
                self._load(index_path, docstore_path)
            else:
                self.create_col(collection_name)

    def _load(self, index_path: str, docstore_path: str):
        """
        Load FAISS index and docstore from disk.

        Args:
            index_path (str): Path to FAISS index file.
            docstore_path (str): Path to docstore pickle file.
        """
        try:
            self.index = faiss.read_index(index_path)
            with open(docstore_path, "rb") as f:
                self.docstore, self.index_to_id = pickle.load(f)
            logger.info(f"Loaded FAISS index from {index_path} with {self.index.ntotal} vectors")
        except Exception as e:
            logger.warning(f"Failed to load FAISS index: {e}")

            self.docstore = {}
            self.index_to_id = {}

    def _save(self):
        """Save FAISS index and docstore to disk."""
        if not self.path or not self.index:
            return

        try:
            os.makedirs(self.path, exist_ok=True)
            index_path = f"{self.path}/{self.collection_name}.faiss"
            docstore_path = f"{self.path}/{self.collection_name}.pkl"

            faiss.write_index(self.index, index_path)
            with open(docstore_path, "wb") as f:
                pickle.dump((self.docstore, self.index_to_id), f)
        except Exception as e:
            logger.warning(f"Failed to save FAISS index: {e}")

    def _parse_output(self, scores, ids, limit=None) -> List[OutputData]:
        """
        Parse the output data.

        Args:
            scores: Similarity scores from FAISS.
            ids: Indices from FAISS.
            limit: Maximum number of results to return.

        Returns:
            List[OutputData]: Parsed output data.
        """
        if limit is None:
            limit = len(ids)

        results = []
        for i in range(min(len(ids), limit)):
            if ids[i] == -1:  # FAISS returns -1 for empty results
                continue

            index_id = int(ids[i])
            vector_id = self.index_to_id.get(index_id)
            if vector_id is None:
                continue

            payload = self.docstore.get(vector_id)
            if payload is None:
                continue

            payload_copy = payload.copy()

            score = float(scores[i])
            entry = OutputData(
                id=vector_id,
                score=score,
                payload=payload_copy,
            )
            results.append(entry)

        return results

    def create_col(self, name: str, distance: str = None):
        """
        Create a new collection.

        Args:
            name (str): Name of the collection.
            distance (str, optional): Distance metric to use. Overrides the distance_strategy
                passed during initialization. Defaults to None.

        Returns:
            self: The FAISS instance.
        """
        distance_strategy = distance or self.distance_strategy

        # Create index based on distance strategy
        if distance_strategy.lower() == "inner_product" or distance_strategy.lower() == "cosine":
            self.index = faiss.IndexFlatIP(self.embedding_model_dims)
        else:
            self.index = faiss.IndexFlatL2(self.embedding_model_dims)

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
        Insert vectors into a collection.

        Args:
            vectors (List[list]): List of vectors to insert.
            payloads (Optional[List[Dict]], optional): List of payloads corresponding to vectors. Defaults to None.
            ids (Optional[List[str]], optional): List of IDs corresponding to vectors. Defaults to None.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]

        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length")

        vectors_np = np.array(vectors, dtype=np.float32)

        if self.normalize_L2 and self.distance_strategy.lower() == "euclidean":
            faiss.normalize_L2(vectors_np)

        self.index.add(vectors_np)

        starting_idx = len(self.index_to_id)
        for i, (vector_id, payload) in enumerate(zip(ids, payloads)):
            self.docstore[vector_id] = payload.copy()
            self.index_to_id[starting_idx + i] = vector_id

        self._save()

        logger.info(f"Inserted {len(vectors)} vectors into collection {self.collection_name}")

    def search(
        self, query: str, vectors: List[list], limit: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query (str): Query (not used, kept for API compatibility).
            vectors (List[list]): List of vectors to search.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Optional[Dict], optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        query_vectors = np.array(vectors, dtype=np.float32)

        if len(query_vectors.shape) == 1:
            query_vectors = query_vectors.reshape(1, -1)

        if self.normalize_L2 and self.distance_strategy.lower() == "euclidean":
            faiss.normalize_L2(query_vectors)

        fetch_k = limit * 2 if filters else limit
        scores, indices = self.index.search(query_vectors, fetch_k)

        results = self._parse_output(scores[0], indices[0], limit)

        if filters:
            filtered_results = []
            for result in results:
                if self._apply_filters(result.payload, filters):
                    filtered_results.append(result)
                    if len(filtered_results) >= limit:
                        break
            results = filtered_results[:limit]

        return results

    def _apply_filters(self, payload: Dict, filters: Dict) -> bool:
        """
        Apply filters to a payload.

        Args:
            payload (Dict): Payload to filter.
            filters (Dict): Filters to apply.

        Returns:
            bool: True if payload passes filters, False otherwise.
        """
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

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        index_to_delete = None
        for idx, vid in self.index_to_id.items():
            if vid == vector_id:
                index_to_delete = idx
                break

        if index_to_delete is not None:
            self.docstore.pop(vector_id, None)
            self.index_to_id.pop(index_to_delete, None)

            self._save()

            logger.info(f"Deleted vector {vector_id} from collection {self.collection_name}")
        else:
            logger.warning(f"Vector {vector_id} not found in collection {self.collection_name}")

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (Optional[List[float]], optional): Updated vector. Defaults to None.
            payload (Optional[Dict], optional): Updated payload. Defaults to None.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if vector_id not in self.docstore:
            raise ValueError(f"Vector {vector_id} not found")

        current_payload = self.docstore[vector_id].copy()

        if payload is not None:
            self.docstore[vector_id] = payload.copy()
            current_payload = self.docstore[vector_id].copy()

        if vector is not None:
            self.delete(vector_id)
            self.insert([vector], [current_payload], [vector_id])
        else:
            self._save()

        logger.info(f"Updated vector {vector_id} in collection {self.collection_name}")

    def get(self, vector_id: str) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if vector_id not in self.docstore:
            return None

        payload = self.docstore[vector_id].copy()

        return OutputData(
            id=vector_id,
            score=None,
            payload=payload,
        )

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        if not self.path:
            return [self.collection_name] if self.index else []

        try:
            collections = []
            path = Path(self.path).parent
            for file in path.glob("*.faiss"):
                collections.append(file.stem)
            return collections
        except Exception as e:
            logger.warning(f"Failed to list collections: {e}")
            return [self.collection_name] if self.index else []

    def delete_col(self):
        """
        Delete a collection.
        """
        if self.path:
            try:
                index_path = f"{self.path}/{self.collection_name}.faiss"
                docstore_path = f"{self.path}/{self.collection_name}.pkl"

                if os.path.exists(index_path):
                    os.remove(index_path)
                if os.path.exists(docstore_path):
                    os.remove(docstore_path)

                logger.info(f"Deleted collection {self.collection_name}")
            except Exception as e:
                logger.warning(f"Failed to delete collection: {e}")

        self.index = None
        self.docstore = {}
        self.index_to_id = {}

    def col_info(self) -> Dict:
        """
        Get information about a collection.

        Returns:
            Dict: Collection information.
        """
        if self.index is None:
            return {"name": self.collection_name, "count": 0}

        return {
            "name": self.collection_name,
            "count": self.index.ntotal,
            "dimension": self.index.d,
            "distance": self.distance_strategy,
        }

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[OutputData]:
        """
        List all vectors in a collection.

        Args:
            filters (Optional[Dict], optional): Filters to apply to the list. Defaults to None.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        if self.index is None:
            return []

        results = []
        count = 0

        for vector_id, payload in self.docstore.items():
            if filters and not self._apply_filters(payload, filters):
                continue

            payload_copy = payload.copy()

            results.append(
                OutputData(
                    id=vector_id,
                    score=None,
                    payload=payload_copy,
                )
            )

            count += 1
            if count >= limit:
                break

        return [results]

    def reset(self):
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name)
