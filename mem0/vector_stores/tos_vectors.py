import json
import logging
import os
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    import tos
except ImportError:
    raise ImportError("The 'tos' library is required. Please install it using 'pip install tos'.")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class TOSVectors(VectorStoreBase):
    def __init__(
        self,
        vector_bucket_name: str,
        collection_name: str,
        embedding_model_dims: int,
        endpoint: str,
        distance_metric: str = "cosine",
        region: str = "cn-beijing",
    ):
        # Get credentials from environment variables
        ak = os.getenv("TOS_ACCESS_KEY")
        sk = os.getenv("TOS_SECRET_KEY")
        account_id = os.getenv("TOS_ACCOUNT_ID")

        if not ak or not sk:
            raise ValueError(
                "TOS_ACCESS_KEY and TOS_SECRET_KEY must be set in environment variables"
            )
        if not account_id:
            raise ValueError("TOS_ACCOUNT_ID must be set in environment variables")

        self.client = tos.VectorClient(ak, sk, endpoint, region)
        self.vector_bucket_name = vector_bucket_name
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        self.account_id = account_id
        self.region = region

        self._ensure_bucket_exists()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)

    def _ensure_bucket_exists(self):
        try:
            self.client.get_vector_bucket(self.vector_bucket_name, self.account_id)
            logger.info(f"Vector bucket '{self.vector_bucket_name}' already exists.")
        except tos.exceptions.TosServerError as e:
            if e.code == "NotFoundException":
                logger.info(f"Vector bucket '{self.vector_bucket_name}' not found. Creating it.")
                self.client.create_vector_bucket(self.vector_bucket_name)
                logger.info(f"Vector bucket '{self.vector_bucket_name}' created.")
            else:
                raise

    def _get_distance_metric_type(self, distance: str):
        """Convert string distance metric to TOS DistanceMetricType."""
        if distance.lower() == "cosine":
            return tos.DistanceMetricType.DistanceMetricCosine
        elif distance.lower() == "euclidean":
            return tos.DistanceMetricType.DistanceMetricEuclidean
        else:
            raise ValueError(f"Unsupported distance metric: {distance}. Use 'cosine' or 'euclidean'.")

    def create_col(self, name, vector_size, distance="cosine"):
        try:
            self.client.get_index(self.vector_bucket_name, self.account_id, name)
            logger.info(f"Index '{name}' already exists in bucket '{self.vector_bucket_name}'.")
        except tos.exceptions.TosServerError as e:
            if e.code == "NotFoundException":
                logger.info(f"Index '{name}' not found in bucket '{self.vector_bucket_name}'. Creating it.")
                distance_metric = self._get_distance_metric_type(distance)
                self.client.create_index(
                    account_id=self.account_id,
                    vector_bucket_name=self.vector_bucket_name,
                    index_name=name,
                    data_type=tos.DataType.DataTypeFloat32,
                    dimension=vector_size,
                    distance_metric=distance_metric,
                )
                logger.info(f"Index '{name}' created.")
            else:
                raise

    def _parse_output(self, vectors: List) -> List[OutputData]:
        results = []
        for v in vectors:
            payload = v.metadata if hasattr(v, 'metadata') else {}
            # Handle metadata as JSON string if needed
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for key {v.key if hasattr(v, 'key') else 'unknown'}")
                    payload = {}
            results.append(
                OutputData(
                    id=v.key if hasattr(v, 'key') else None,
                    score=v.distance if hasattr(v, 'distance') else None,
                    payload=payload
                )
            )
        return results

    def insert(self, vectors, payloads=None, ids=None):
        vectors_to_put = []
        for i, vec in enumerate(vectors):
            vector_obj = tos.models2.Vector(
                key=ids[i],
                data=tos.models2.VectorData(float32=vec),
                metadata=payloads[i] if payloads else {},
            )
            vectors_to_put.append(vector_obj)

        self.client.put_vectors(
            vector_bucket_name=self.vector_bucket_name,
            account_id=self.account_id,
            index_name=self.collection_name,
            vectors=vectors_to_put,
        )

    def search(self, query, vectors, limit=5, filters=None):
        query_vector = tos.models2.VectorData(float32=vectors)
        params = {
            "vector_bucket_name": self.vector_bucket_name,
            "account_id": self.account_id,
            "index_name": self.collection_name,
            "query_vector": query_vector,
            "top_k": limit,
            "return_distance": True,
            "return_metadata": True,
        }
        if filters:
            params["filter"] = filters

        response = self.client.query_vectors(**params)
        return self._parse_output(response.vectors if hasattr(response, 'vectors') else [])

    def delete(self, vector_id):
        self.client.delete_vectors(
            vector_bucket_name=self.vector_bucket_name,
            account_id=self.account_id,
            index_name=self.collection_name,
            keys=[vector_id],
        )

    def update(self, vector_id, vector=None, payload=None):
        # TOS Vectors uses put_vectors for updates (overwrite)
        self.insert(vectors=[vector], payloads=[payload], ids=[vector_id])

    def get(self, vector_id) -> Optional[OutputData]:
        response = self.client.get_vectors(
            vector_bucket_name=self.vector_bucket_name,
            account_id=self.account_id,
            index_name=self.collection_name,
            keys=[vector_id],
            return_data=False,
            return_metadata=True,
        )
        vectors = response.vectors if hasattr(response, 'vectors') else []
        if not vectors:
            return None
        return self._parse_output(vectors)[0]

    def list_cols(self):
        response = self.client.list_indexes(self.vector_bucket_name, self.account_id)
        indexes = response.indexes if hasattr(response, 'indexes') else []
        return [idx.index_name for idx in indexes]

    def delete_col(self):
        self.client.delete_index(self.vector_bucket_name, self.account_id, self.collection_name)

    def col_info(self):
        response = self.client.get_index(self.vector_bucket_name, self.account_id, self.collection_name)
        return response.index if hasattr(response, 'index') else {}

    def list(self, filters=None, limit=None):
        # Note: list_vectors does not support metadata filtering.
        if filters:
            logger.warning("TOS Vectors `list` does not support metadata filtering. Ignoring filters.")

        params = {
            "vector_bucket_name": self.vector_bucket_name,
            "index_name": self.collection_name,
            "account_id": self.account_id,
            "return_data": False,
            "return_metadata": True,
        }
        if limit:
            params["max_results"] = limit

        # Handle pagination
        all_vectors = []
        next_token = None
        while True:
            if next_token:
                params["next_token"] = next_token

            response = self.client.list_vectors(**params)
            vectors = response.vectors if hasattr(response, 'vectors') else []
            all_vectors.extend(vectors)

            # Check if there are more results
            next_token = response.next_token if hasattr(response, 'next_token') else None
            if not next_token or (limit and len(all_vectors) >= limit):
                break

        return [self._parse_output(all_vectors)]

    def reset(self):
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)
