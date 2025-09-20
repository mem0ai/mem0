import json
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    raise ImportError("The 'boto3' library is required. Please install it using 'pip install boto3'.")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class S3Vectors(VectorStoreBase):
    def __init__(
        self,
        vector_bucket_name: str,
        collection_name: str,
        embedding_model_dims: int,
        distance_metric: str = "cosine",
        region_name: Optional[str] = None,
    ):
        self.client = boto3.client("s3vectors", region_name=region_name)
        self.vector_bucket_name = vector_bucket_name
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric

        self._ensure_bucket_exists()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)

    def _ensure_bucket_exists(self):
        try:
            self.client.get_vector_bucket(vectorBucketName=self.vector_bucket_name)
            logger.info(f"Vector bucket '{self.vector_bucket_name}' already exists.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                logger.info(f"Vector bucket '{self.vector_bucket_name}' not found. Creating it.")
                self.client.create_vector_bucket(vectorBucketName=self.vector_bucket_name)
                logger.info(f"Vector bucket '{self.vector_bucket_name}' created.")
            else:
                raise

    def create_col(self, name, vector_size, distance="cosine"):
        try:
            self.client.get_index(vectorBucketName=self.vector_bucket_name, indexName=name)
            logger.info(f"Index '{name}' already exists in bucket '{self.vector_bucket_name}'.")
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                logger.info(f"Index '{name}' not found in bucket '{self.vector_bucket_name}'. Creating it.")
                self.client.create_index(
                    vectorBucketName=self.vector_bucket_name,
                    indexName=name,
                    dataType="float32",
                    dimension=vector_size,
                    distanceMetric=distance,
                )
                logger.info(f"Index '{name}' created.")
            else:
                raise

    def _parse_output(self, vectors: List[Dict]) -> List[OutputData]:
        results = []
        for v in vectors:
            payload = v.get("metadata", {})
            # Boto3 might return metadata as a JSON string
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except json.JSONDecodeError:
                    logger.warning(f"Failed to parse metadata for key {v.get('key')}")
                    payload = {}
            results.append(OutputData(id=v.get("key"), score=v.get("distance"), payload=payload))
        return results

    def insert(self, vectors, payloads=None, ids=None):
        vectors_to_put = []
        for i, vec in enumerate(vectors):
            vectors_to_put.append(
                {
                    "key": ids[i],
                    "data": {"float32": vec},
                    "metadata": payloads[i] if payloads else {},
                }
            )
        self.client.put_vectors(
            vectorBucketName=self.vector_bucket_name,
            indexName=self.collection_name,
            vectors=vectors_to_put,
        )

    def search(self, query, vectors, limit=5, filters=None):
        params = {
            "vectorBucketName": self.vector_bucket_name,
            "indexName": self.collection_name,
            "queryVector": {"float32": vectors},
            "topK": limit,
            "returnMetadata": True,
            "returnDistance": True,
        }
        if filters:
            params["filter"] = filters

        response = self.client.query_vectors(**params)
        return self._parse_output(response.get("vectors", []))

    def delete(self, vector_id):
        self.client.delete_vectors(
            vectorBucketName=self.vector_bucket_name,
            indexName=self.collection_name,
            keys=[vector_id],
        )

    def update(self, vector_id, vector=None, payload=None):
        # S3 Vectors uses put_vectors for updates (overwrite)
        self.insert(vectors=[vector], payloads=[payload], ids=[vector_id])

    def get(self, vector_id) -> Optional[OutputData]:
        response = self.client.get_vectors(
            vectorBucketName=self.vector_bucket_name,
            indexName=self.collection_name,
            keys=[vector_id],
            returnData=False,
            returnMetadata=True,
        )
        vectors = response.get("vectors", [])
        if not vectors:
            return None
        return self._parse_output(vectors)[0]

    def list_cols(self):
        response = self.client.list_indexes(vectorBucketName=self.vector_bucket_name)
        return [idx["indexName"] for idx in response.get("indexes", [])]

    def delete_col(self):
        self.client.delete_index(vectorBucketName=self.vector_bucket_name, indexName=self.collection_name)

    def col_info(self):
        response = self.client.get_index(vectorBucketName=self.vector_bucket_name, indexName=self.collection_name)
        return response.get("index", {})

    def list(self, filters=None, limit=None):
        # Note: list_vectors does not support metadata filtering.
        if filters:
            logger.warning("S3 Vectors `list` does not support metadata filtering. Ignoring filters.")

        params = {
            "vectorBucketName": self.vector_bucket_name,
            "indexName": self.collection_name,
            "returnData": False,
            "returnMetadata": True,
        }
        if limit:
            params["maxResults"] = limit

        paginator = self.client.get_paginator("list_vectors")
        pages = paginator.paginate(**params)
        all_vectors = []
        for page in pages:
            all_vectors.extend(page.get("vectors", []))
        return [self._parse_output(all_vectors)]

    def reset(self):
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_metric)
