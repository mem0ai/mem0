import json
import logging
import os
import pickle
import uuid
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    import pyvsag
except ImportError:
    raise ImportError(
        "Could not import pyvsag package. "
        "Please install it with `pip install pyvsag`"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class VSAG(VectorStoreBase):
    """VSAG vector store implementation for mem0."""

    def __init__(
        self,
        collection_name: str = "mem0",
        path: Optional[str] = None,
        dim: int = 1536,
        index_type: str = "hnsw",
        metric_type: str = "l2",
        dtype: str = "float32",
        index_params: Optional[Dict] = None,
        search_params: Optional[Dict] = None,
    ):
        """
        Initialize VSAG vector store.

        Args:
            collection_name: Name of the collection
            path: Path to store index and metadata
            dim: Dimension of vectors
            index_type: Type of VSAG index (hnsw, hgraph, diskann, ivf, etc.)
            metric_type: Distance metric (l2, ip, cosine)
            dtype: Data type for vectors (float32, int8)
            index_params: Additional index parameters
            search_params: Default search parameters
        """
        self.collection_name = collection_name
        self.path = path or f"/tmp/vsag/{collection_name}"
        self.dim = dim
        self.index_type = index_type
        self.metric_type = metric_type
        self.dtype = dtype
        self.search_params = search_params or {}

        # Build default index params based on index type
        self.index_params = index_params or self._get_default_index_params()

        # Storage for payload and id mapping
        self.docstore: Dict[str, Dict] = {}  # id -> payload
        self.id_to_internal: Dict[str, int] = {}  # external_id -> internal_id
        self.internal_to_id: Dict[int, str] = {}  # internal_id -> external_id
        self.vectors: List[np.ndarray] = []  # Store vectors for update/get operations
        self._next_internal_id = 0

        # Index instance
        self.index: Optional[pyvsag.Index] = None

        # Create directory
        os.makedirs(self.path, exist_ok=True)

        # Try to load existing index
        index_file = os.path.join(self.path, f"{collection_name}.index")
        meta_file = os.path.join(self.path, f"{collection_name}.meta")

        if os.path.exists(index_file) and os.path.exists(meta_file):
            self._load(index_file, meta_file)
        else:
            self.create_col(collection_name)

    def _get_default_index_params(self) -> Dict:
        """Get default index parameters based on index type."""
        defaults = {
            "hnsw": {"max_degree": 16, "ef_construction": 100},
            "hgraph": {
                "base_quantization_type": "sq8",
                "max_degree": 26,
                "ef_construction": 100,
            },
            "ivf": {"n_clusters": 100},
            "diskann": {},
        }
        return defaults.get(self.index_type, {})

    def _build_index_params_json(self) -> str:
        """Build JSON string for VSAG index parameters."""
        params = {
            "dtype": self.dtype,
            "metric_type": self.metric_type,
            "dim": self.dim,
            self.index_type: self.index_params,
        }
        return json.dumps(params)

    def _get_search_params_json(self, custom_params: Optional[Dict] = None) -> str:
        """Build JSON string for search parameters."""
        params = custom_params or self.search_params
        if not params:
            # Default search params based on index type
            defaults = {
                "hnsw": {"ef_search": 100},
                "hgraph": {"ef_search": 100},
            }
            params = defaults.get(self.index_type, {})
        return json.dumps({self.index_type: params} if params else {})

    def create_col(self, name: str, vector_size: Optional[int] = None, distance: Optional[str] = None):
        """
        Create a new collection.

        Args:
            name: Name of the collection
            vector_size: Dimension of vectors (uses self.dim if not specified)
            distance: Distance metric (uses self.metric_type if not specified)
        """
        if vector_size:
            self.dim = vector_size
        if distance:
            self.metric_type = distance

        self.collection_name = name
        index_params_json = self._build_index_params_json()

        try:
            self.index = pyvsag.Index(self.index_type, index_params_json)
            logger.info(f"Created VSAG index: type={self.index_type}, dim={self.dim}, metric={self.metric_type}")
        except Exception as e:
            logger.error(f"Failed to create VSAG index: {e}")
            raise

        return self

    def _save(self):
        """Save index and metadata to disk."""
        if not self.path or not self.index:
            return

        try:
            index_file = os.path.join(self.path, f"{self.collection_name}.index")
            meta_file = os.path.join(self.path, f"{self.collection_name}.meta")

            self.index.save(index_file)

            with open(meta_file, "wb") as f:
                pickle.dump({
                    "docstore": self.docstore,
                    "id_to_internal": self.id_to_internal,
                    "internal_to_id": self.internal_to_id,
                    "vectors": self.vectors,
                    "_next_internal_id": self._next_internal_id,
                    "dim": self.dim,
                }, f)

            logger.info(f"Saved VSAG index to {self.path}")
        except Exception as e:
            logger.warning(f"Failed to save VSAG index: {e}")

    def _load(self, index_file: str, meta_file: str):
        """Load index and metadata from disk."""
        try:
            index_params_json = self._build_index_params_json()
            self.index = pyvsag.Index(self.index_type, index_params_json)
            self.index.load(index_file)

            with open(meta_file, "rb") as f:
                meta = pickle.load(f)
                self.docstore = meta["docstore"]
                self.id_to_internal = meta["id_to_internal"]
                self.internal_to_id = meta["internal_to_id"]
                self.vectors = meta["vectors"]
                self._next_internal_id = meta["_next_internal_id"]
                self.dim = meta["dim"]

            logger.info(f"Loaded VSAG index from {self.path} with {len(self.docstore)} vectors")
        except Exception as e:
            logger.warning(f"Failed to load VSAG index: {e}")
            self.docstore = {}
            self.id_to_internal = {}
            self.internal_to_id = {}
            self.vectors = []
            self._next_internal_id = 0
            self.create_col(self.collection_name)

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors: List of vectors to insert
            payloads: List of payloads corresponding to vectors
            ids: List of IDs corresponding to vectors
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]

        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length")

        # Convert to numpy array
        vectors_np = np.array(vectors, dtype=np.float32)

        # Assign internal IDs
        internal_ids = []
        for ext_id in ids:
            if ext_id in self.id_to_internal:
                logger.warning(f"ID {ext_id} already exists, skipping")
                continue
            internal_ids.append(self._next_internal_id)
            self._next_internal_id += 1

        if not internal_ids:
            return

        # Store metadata
        for i, (ext_id, payload, vector) in enumerate(zip(ids, payloads, vectors)):
            int_id = internal_ids[i]
            self.docstore[ext_id] = payload.copy()
            self.id_to_internal[ext_id] = int_id
            self.internal_to_id[int_id] = ext_id
            self.vectors.append(np.array(vector, dtype=np.float32))

        # Add to index
        try:
            ids_array = np.array(internal_ids, dtype=np.int64)
            self.index.add(
                vectors=vectors_np.flatten(),
                ids=ids_array,
                num_elements=len(internal_ids),
                dim=self.dim
            )
            self._save()
            logger.info(f"Inserted {len(internal_ids)} vectors into collection {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise

    def search(
        self,
        query: str,
        vectors: List[List[float]],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query: Query string (not used, kept for API compatibility)
            vectors: Query vectors
            limit: Number of results to return
            filters: Filters to apply

        Returns:
            List of OutputData with search results
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        query_vector = np.array(vectors[0], dtype=np.float32)
        search_params_json = self._get_search_params_json()

        try:
            result_ids, result_dists = self.index.knn_search(
                vector=query_vector,
                k=limit * 2 if filters else limit,  # Fetch more if filtering
                parameters=search_params_json
            )
        except Exception as e:
            logger.error(f"Search failed: {e}")
            return []

        results = []
        for int_id, dist in zip(result_ids, result_dists):
            ext_id = self.internal_to_id.get(int_id)
            if ext_id is None:
                continue

            payload = self.docstore.get(ext_id)
            if payload is None:
                continue

            # Apply filters
            if filters and not self._apply_filters(payload, filters):
                continue

            results.append(OutputData(
                id=ext_id,
                score=float(dist),
                payload=payload.copy(),
            ))

            if len(results) >= limit:
                break

        return results

    def _apply_filters(self, payload: Dict, filters: Dict) -> bool:
        """Apply filters to a payload."""
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
            vector_id: ID of the vector to delete
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if vector_id not in self.id_to_internal:
            logger.warning(f"Vector {vector_id} not found")
            return

        int_id = self.id_to_internal[vector_id]

        try:
            # Remove from VSAG index
            self.index.remove(np.array([int_id], dtype=np.int64))

            # Remove from metadata
            del self.docstore[vector_id]
            del self.id_to_internal[vector_id]
            del self.internal_to_id[int_id]

            self._save()
            logger.info(f"Deleted vector {vector_id} from collection {self.collection_name}")
        except Exception as e:
            logger.warning(f"Failed to delete vector {vector_id}: {e}")

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id: ID of the vector to update
            vector: Updated vector (if None, only payload is updated)
            payload: Updated payload (if None, only vector is updated)
        """
        if self.index is None:
            raise ValueError("Collection not initialized. Call create_col first.")

        if vector_id not in self.docstore:
            raise ValueError(f"Vector {vector_id} not found")

        # Update payload
        if payload is not None:
            self.docstore[vector_id] = payload.copy()

        # Update vector requires remove + add
        if vector is not None:
            old_payload = self.docstore.get(vector_id, {})
            self.delete(vector_id)
            self.insert([vector], [old_payload], [vector_id])

        self._save()
        logger.info(f"Updated vector {vector_id} in collection {self.collection_name}")

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id: ID of the vector to retrieve

        Returns:
            OutputData with the vector, or None if not found
        """
        if vector_id not in self.docstore:
            return None

        payload = self.docstore[vector_id].copy()

        return OutputData(
            id=vector_id,
            score=None,
            payload=payload,
        )

    def list_cols(self) -> List[str]:
        """List all collections."""
        if not self.path:
            return [self.collection_name]

        try:
            collections = []
            for file in Path(self.path).glob("*.index"):
                collections.append(file.stem)
            return collections
        except Exception:
            return [self.collection_name]

    def delete_col(self):
        """Delete the collection."""
        if self.path:
            try:
                index_file = os.path.join(self.path, f"{self.collection_name}.index")
                meta_file = os.path.join(self.path, f"{self.collection_name}.meta")

                if os.path.exists(index_file):
                    os.remove(index_file)
                if os.path.exists(meta_file):
                    os.remove(meta_file)

                logger.info(f"Deleted collection {self.collection_name}")
            except Exception as e:
                logger.warning(f"Failed to delete collection: {e}")

        self.index = None
        self.docstore = {}
        self.id_to_internal = {}
        self.internal_to_id = {}
        self.vectors = []
        self._next_internal_id = 0

    def col_info(self) -> Dict:
        """Get information about the collection."""
        if self.index is None:
            return {"name": self.collection_name, "count": 0}

        try:
            num_elements = self.index.get_num_elements()
        except Exception:
            num_elements = len(self.docstore)

        return {
            "name": self.collection_name,
            "count": num_elements,
            "dimension": self.dim,
            "metric": self.metric_type,
            "index_type": self.index_type,
        }

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[List[OutputData]]:
        """
        List all vectors in the collection.

        Args:
            filters: Filters to apply
            limit: Maximum number of vectors to return

        Returns:
            List of lists containing OutputData
        """
        results = []
        count = 0

        for vector_id, payload in self.docstore.items():
            if filters and not self._apply_filters(payload, filters):
                continue

            results.append(OutputData(
                id=vector_id,
                score=None,
                payload=payload.copy(),
            ))

            count += 1
            if count >= limit:
                break

        return [results]

    def reset(self):
        """Reset by deleting and recreating the collection."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name)