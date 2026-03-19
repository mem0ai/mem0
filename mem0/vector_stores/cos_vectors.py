import json
import logging
from typing import Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

try:
    from qcloud_cos import CosConfig, CosVectorsClient
    from qcloud_cos import CosServiceError
except ImportError:
    raise ImportError("The 'cos-python-sdk-v5>=1.9.41' library is required. Please install it using 'pip install cos-python-sdk-v5>=1.9.41'.")

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class CosVectors(VectorStoreBase):
    def __init__(
        self,
        bucket_name: str,
        collection_name: str,
        region: str,
        embedding_model_dims: int,
        secret_id: str,
        secret_key: str,
        token: Optional[str] = None,
        distance_metric: str = "cosine",
        internal_access: bool = False,
    ):
        self.bucket_name = bucket_name
        self.index_name = collection_name
        self.region = region
        self.secret_id = secret_id
        self.secret_key = secret_key
        self.token = token
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        self.internal_access = internal_access

        self._init_client()
        self._ensure_bucket_exists()
        self.create_col(self.index_name, self.embedding_model_dims, self.distance_metric)

    def _init_client(self):
        config = CosConfig(
            Region=self.region,
            SecretId=self.secret_id, 
            SecretKey=self.secret_key,
            Token=self.token,
            Scheme="http",
            Domain=self._get_endpoint(),
        )
        self.client = CosVectorsClient(config)

    def _get_endpoint(self):
        if self.internal_access:
            return f"vectors.{self.region}.internal.tencentcos.com"
        else:
            return f"vectors.{self.region}.coslake.com"

    def _ensure_bucket_exists(self):
        try:
            self.client.get_vector_bucket(Bucket=self.bucket_name)
            logger.info(f"Vector bucket '{self.bucket_name}' already exists.")
        except CosServiceError as e:
            if e.get_error_code() == "NotFoundException":
                logger.info(f"Vector bucket '{self.bucket_name}' not found. Creating it.")
                self.client.create_vector_bucket(Bucket=self.bucket_name)
                logger.info(f"Vector bucket '{self.bucket_name}' created.")
            else:
                raise

    def create_col(self, name, vector_size, distance="cosine"):
        try:
            self.client.get_index(Bucket=self.bucket_name, Index=name)
            logger.info(f"Index '{name}' already exists in bucket '{self.bucket_name}'.")
        except CosServiceError as e:
            if e.get_error_code() == "NotFoundException":
                logger.info(f"Index '{name}' not found in bucket '{self.bucket_name}'. Creating it.")
                self.client.create_index(
                    Bucket=self.bucket_name,
                    Index=name,
                    DataType="float32",
                    Dimension=vector_size,
                    DistanceMetric=distance,
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
            Bucket=self.bucket_name,
            Index=self.index_name,
            Vectors=vectors_to_put,
        )

    def search(self, query, vectors, limit=5, filters=None):
        print(len(vectors))
        _, data = self.client.query_vectors(
            Bucket=self.bucket_name,
            Index=self.index_name,
            QueryVector={"float32": vectors},
            TopK=limit,
            ReturnMetaData=True,
            ReturnDistance=True,
            Filter=filters,
        )
        return self._parse_output(data.get("vectors", []))

    def delete(self, vector_id):
        self.client.delete_vectors(
            Bucket=self.bucket_name,
            Index=self.index_name,
            keys=[vector_id],
        )

    def update(self, vector_id, vector=None, payload=None):
        # Cos Vectors uses put_vectors for updates (overwrite)
        self.insert(vectors=[vector], payloads=[payload], ids=[vector_id])

    def get(self, vector_id) -> Optional[OutputData]:
        _, data = self.client.get_vectors(
            Bucket=self.bucket_name,
            Index=self.index_name,
            keys=[vector_id],
            returnData=False,
            returnMetadata=True,
        )
        vectors = data.get("vectors", [])
        if not vectors:
            return None
        return self._parse_output(vectors)[0]

    def list_cols(self):
        _, data = self.client.list_indexes(Bucket=self.bucket_name)
        return [idx["indexName"] for idx in data.get("indexes", [])]

    def delete_col(self):
        self.client.delete_index(Bucket=self.bucket_name, Index=self.index_name)

    def col_info(self):
        _, data = self.client.get_index(Bucket=self.bucket_name, Index=self.index_name)
        return data.get("index", {})

    def list(self, filters=None, limit=None):
        # Note: list_vectors does not support metadata filtering.
        if filters:
            logger.warning("Cos Vectors `list` does not support metadata filtering. Ignoring filters.")
            
        next_token = None
        finished = False
        all_vectors = []
        while not finished:
            if limit is not None:
                remaining = limit - len(all_vectors)
                batch_size = min(remaining, 1000)
            else:
                batch_size = 1000

            _, data = self.client.list_vectors(
                Bucket=self.bucket_name,
                Index=self.index_name,
                ReturnData=False,
                ReturnMetaData=True,
                NextToken=next_token,
                MaxResults=batch_size,
            )
            all_vectors.extend(data.get("vectors", []))

            if limit is not None and len(all_vectors) >= limit:
                all_vectors = all_vectors[:limit]
                finished = True
            elif data.get("nextToken"):
                next_token = data.get("nextToken")
            else:
                finished = True
        
        return self._parse_output(all_vectors)

    def reset(self):
        logger.warning(f"Resetting index {self.index_name}...")
        self.delete_col()
        self.create_col(self.index_name, self.embedding_model_dims, self.distance_metric)
