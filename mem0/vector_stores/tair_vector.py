import json
import threading
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from functools import reduce
from typing import List, Optional, Dict

import pytz
from redis.connection import ConnectionPool
from mem0.vector_stores.base import VectorStoreBase
from datetime import datetime
from tair import Tair
from tair.tairvector import DistanceMetric, IndexType
import logging

logger = logging.getLogger(__name__)


class TairVectorExtendClient(Tair):
    KNNSEARCHFIELD = "TVS.KNNSEARCHFIELD"

    @classmethod
    def from_url(cls, url: str, **kwargs):
        connection_pool = ConnectionPool.from_url(url, **kwargs)
        return cls(connection_pool=connection_pool)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def tvs_knnsearchfield(self, index: str, k: int, vector: List[float], field_count: int = 0,
                           field_names: List[str] = None, filter_str: str = None, is_binary: bool = False, **kwargs):
        """
        search for the top @k approximate nearest neighbors of @vector in an index, return with field information
        """
        params = reduce(lambda x, y: x + y, kwargs.items(), ())
        if field_names is None:
            field_names = []
        if field_count != 0 and field_count != len(field_names):
            raise ValueError("field_count must be 0 or equal to the number of field_names")
        if not (isinstance(vector, str) or isinstance(vector, bytes)):
            vector = self.encode_vector(vector, is_binary)
        if filter_str:
            return self.execute_command(self.KNNSEARCHFIELD, index, k, vector, field_count, *field_names,
                                        filter_str, *params)
        else:
            return self.execute_command(self.KNNSEARCHFIELD, index, k, vector, field_count, *field_names, *params)


class MemoryResult:
    def __init__(self, id: str, score: float = None, payload: Dict = None):
        self.id = id
        self.score = score
        self.payload = payload

    @staticmethod
    def safe_decode(value):
        if isinstance(value, bytes):
            return value.decode()
        return value

    @classmethod
    def from_list(cls, data: List):
        id = cls.safe_decode(data[0])
        score = float(cls.safe_decode(data[1]))
        payload = {}
        i = 2
        while i < len(data):
            key = cls.safe_decode(data[i])
            if key == 'VECTOR':
                i += 2
                continue
            elif key == "metadata":
                payload[key] = json.loads(cls.safe_decode(data[i + 1]))
            elif key == 'TEXT':
                payload["data"] = cls.safe_decode(data[i + 1])
            elif key == 'created_at' or key == "updated_at":
                payload[key] = datetime.fromtimestamp(
                    int(cls.safe_decode(data[i + 1])),
                    tz=pytz.timezone("US/Pacific")
                ).isoformat(timespec="microseconds")
            else:
                payload[key] = cls.safe_decode(data[i + 1])
            i += 2
        return cls(id, score, payload)

    @classmethod
    def from_fields_dict(cls, id: str, data: Dict):
        payload = {}
        for key, value in data.items():
            if key == 'VECTOR':
                continue
            elif key == 'metadata':
                payload[key] = json.loads(value)
            elif key == 'TEXT':
                payload["data"] = value
            elif key == 'created_at' or key == "updated_at":
                payload[key] = datetime.fromtimestamp(
                    int(value),
                    tz=pytz.timezone("US/Pacific")
                ).isoformat(timespec="microseconds")
            else:
                payload[key] = value
        return cls(id, score=0, payload=payload)

    @classmethod
    def from_tuple_values(cls, data: tuple):
        return cls(
            id=data[0],
            score=data[1],
            payload=None,
        )


# all field excludes metadata and data
ALL_FIELDS = ["memory_id", "hash", "user_id", "agent_id", "run_id", "actor_id", "created_at", "updated_at", "role"]

# memory_id and hash are fields that unique to each memory.
INVERTED_INDEX_FIELDS_TYPE = {
    "agent_id": "string",
    "run_id": "string",
    "actor_id": "string",
    "created_at": "long",
    "updated_at": "long",
}

MULTI_INDEX_MODE_COLLECTION_PREFIX = "mem0_vector_index"


class TairVector(VectorStoreBase):
    def __init__(
            self,
            host: str,
            port: int,
            db: str,
            username: str,
            password: str,
            collection_name: str,
            embedding_model_dims: int = 1536,
            distance_method: DistanceMetric = DistanceMetric.L2
    ):
        """
        Args:
            host: tair host
            port: tair port, default port is
            db:  tair DB name, default name is "mem0"
            username:
            password:
            embedding_model_dims:
        """
        self.connection_info = {
            "host": host,
            "port": port,
            "db": db,
            "username": username,
            "password": password,
        }
        self.collection_name = collection_name
        self.tair_client = TairVectorExtendClient(host=host, port=port, db=db, username=username, password=password)
        self.embedding_model_dims = embedding_model_dims
        self.distance_method = distance_method
        self.index_params = {
            "index_type": IndexType.FLAT,
            "data_type": "Float16",
            "lexical_algorithm": "bm25"
        }
        self.pool = ThreadPoolExecutor(max_workers=10)
        self.local = threading.local()
        self._ensure_collection_exists(collection_name, vector_size=embedding_model_dims, distance=distance_method)

    def _get_client(self):
        if not hasattr(self.local, 'client'):
            self.local.client = TairVectorExtendClient(**self.connection_info)
        return self.local.client

    def _ensure_collection_exists(self, name: str, vector_size: int,
                                  distance: DistanceMetric = DistanceMetric.Cosine) -> None:
        """Ensure that a collection exists, creating it if necessary."""
        try:
            if not self._index_exists(name):
                self._create_collection(name, vector_size, distance)
            else:
                logger.info(f"Collection {name} already exists.")
        except Exception as e:
            logger.error(f"Error ensuring collection {name} exists: {str(e)}")
            raise

    def _index_exists(self, name: str) -> bool:
        """Check if an index exists."""
        try:
            return self.tair_client.tvs_get_index(name) is not None
        except Exception as e:
            logger.error(f"Error checking if index {name} exists: {str(e)}")
            raise

    def _create_collection(self, name: str, vector_size: int, distance: DistanceMetric) -> None:
        """Create a new collection."""
        try:
            index_param = deepcopy(self.index_params)
            index_param["distance_type"] = distance

            for field, data_type in INVERTED_INDEX_FIELDS_TYPE.items():
                index_param[f"inverted_index_{field}"] = data_type

            ret = self.tair_client.tvs_create_index(name, vector_size, **index_param)
            if not ret:
                raise ValueError(f"Failed to create index {name}")
            logger.info(f"Collection {name} created successfully")
        except Exception as e:
            logger.error(f"Error creating collection {name}: {str(e)}")
            raise

    def create_col(self, name: str, vector_size: int, distance: DistanceMetric = DistanceMetric.Cosine) -> None:
        """Create a new collection."""
        self._ensure_collection_exists(name, vector_size, distance)

    def _insert_single(self, vector: List[float], payload: Dict, vector_id: str):
        client = self._get_client()
        if payload is None:
            payload = {}

        if "created_at" not in payload:
            payload["created_at"] = datetime.now().isoformat()

        collection_name = self.collection_name
        if "user_id" in payload and payload["user_id"]:
            # call create_col() each time to avoid index missing
            collection_name = f"{MULTI_INDEX_MODE_COLLECTION_PREFIX}_{payload['user_id']}"
            self._ensure_collection_exists(collection_name, vector_size=self.embedding_model_dims, distance=self.distance_method)
            payload.pop("user_id")

        entry = {}
        for key, value in payload.items():
            if key in ["agent_id", "run_id", "actor_id"]:
                entry[key] = str(value)
            elif key == "data":
                entry["TEXT"] = value
            elif key == "created_at":
                entry["created_at"] = int(datetime.fromisoformat(value).timestamp())
            elif value is not None:
                entry[key] = value

        client.tvs_hset(collection_name, vector_id, vector, is_binary=False, **entry)
        # store the vector_id -> collection_name mapping
        client.set(vector_id, collection_name)

    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None,
               ids: Optional[List[str]] = None) -> None:
        """Insert vectors into a collection."""
        try:
            futures = [self.pool.submit(self._insert_single, vector, payload, vector_id)
                       for vector, payload, vector_id in zip(vectors, payloads, ids)]
            for future in futures:
                future.result()
        except Exception as e:
            logger.error(f"Error inserting vectors: {str(e)}")
            raise

    def search(self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None
               ) -> List[MemoryResult]:
        """Search for similar vectors."""
        if filters and 'user_id' in filters:
            collection_name = f"{MULTI_INDEX_MODE_COLLECTION_PREFIX}_{filters['user_id']}"
            filters.pop('user_id')
        else:
            collection_name = self.collection_name

        conditions = []
        if filters is not None:
            for key, value in filters.items():
                if value is not None:
                    if isinstance(value, str):
                        conditions.append(f"{key} == \"{value}\"")
                    else:
                        conditions.append(f"{key} == {value}")

        if conditions:
            filter_str = reduce(lambda x, y: f"{x} && {y}", conditions)
        else:
            filter_str = None

        kwargs = {
            "TEXT": query,
            "hybrid_ratio": 0.5,
        }

        # search all field
        if self.tair_client.tvs_get_index(collection_name):
            results = self.tair_client.tvs_knnsearchfield(
                index=collection_name,
                k=limit,
                vector=vectors,
                filter_str=filter_str,
                **kwargs
            )

            return [
                MemoryResult.from_list(result)
                for result in results
            ]
        else:
            return []

    def delete(self, vector_id: str) -> None:
        """Delete a vector by ID."""
        collection_name = self.tair_client.get(vector_id)
        if collection_name:
            self.tair_client.tvs_del(collection_name, vector_id)
            self.tair_client.delete(vector_id)
        else:
            logger.info(f"Collection {collection_name} not found. Skipping deletion")
        return None

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None
               ) -> None:
        """Update a vector and its payload."""
        if payload is None:
            payload = {}

        if "updated_at" not in payload:
            payload["updated_at"] = datetime.now().isoformat()

        collection_name = self.tair_client.get(vector_id)
        if collection_name is None:
            logger.info(f"Collection not found for vector_id: {vector_id}")
            return None

        entry = {}
        for key, value in payload.items():
            if key in ["agent_id", "run_id", "actor_id"]:
                entry[key] = str(value)
            elif key == "created_at" or key == "updated_at":
                entry[key] = int(datetime.fromisoformat(value).timestamp())
            elif key == "data":
                entry["TEXT"] = value
            elif value is not None:
                entry[key] = value

        self.tair_client.tvs_hset(collection_name, vector_id, vector, is_binary=False, **entry)

    def get(self, vector_id) -> Optional[MemoryResult]:
        """Retrieve a vector by ID."""
        collection_name = self.tair_client.get(vector_id)
        if collection_name:
            ret = self.tair_client.tvs_hgetall(collection_name, vector_id)
            return MemoryResult.from_fields_dict(vector_id, ret)
        else:
            logger.info(f"Collection {collection_name} not found. Skipping deletion")
            return None

    def list_cols(self) -> List[str]:
        """List all mem0 collections."""
        result = self.tair_client.tvs_scan_index()
        indices = []
        for index in result.iter():
            index_name = index.decode()
            if index_name != self.collection_name and not index_name.startswith(MULTI_INDEX_MODE_COLLECTION_PREFIX):
                continue
            indices.append(index.decode())
        return indices

    def delete_col(self) -> None:
        """Delete all collection."""
        for index in self.list_cols():
            self.tair_client.tvs_del_index(index)
        self.tair_client.flushall()

    def col_info(self) -> Dict:
        """Get information about all the collection."""
        result = {}
        for collection in self.list_cols():
            result[collection] = self.tair_client.tvs_get_index(collection)
        return result

    def _get_single_memory(self, memory_id: str) -> Optional[MemoryResult]:
        client = self._get_client()
        collection_name = self.tair_client.get(memory_id)
        if collection_name is None:
            logger.info(f"Collection not found for memory_id: {memory_id}")
            return None

        all_field_value = client.tvs_hgetall(collection_name, memory_id)
        if not all_field_value:
            logger.info(f"Memory not found for memory_id: {memory_id}")
            return None

        payload = {}
        for field, value in all_field_value.items():
            if value is None:
                continue
            elif field == "TEXT":
                payload["data"] = value
            elif field == "created_at" or field == "updated_at":
                try:
                    payload[field] = datetime.fromtimestamp(int(value)).isoformat(timespec="microseconds")
                except ValueError:
                    logger.warning(f"Invalid timestamp for {field}: {value}")
                    payload[field] = None
            else:
                payload[field] = value

        return MemoryResult(
            id=memory_id,
            payload=payload
        )

    def list(self, filters=None, limit=None) -> list:
        """List all memories."""
        conditions = []
        if filters is not None:
            for key, value in filters.items():
                if key == "user_id":
                    continue
                if value is not None:
                    if isinstance(value, str):
                        conditions.append(f"{key} == \"{value}\"")
                    else:
                        conditions.append(f"{key} == {value}")
        if conditions:
            filter_str = reduce(lambda x, y: f"{x} && {y}", conditions)
        else:
            filter_str = None

        if limit is None:
            limit = 20

        if filters and 'user_id' in filters:
            # scan this collection
            collection_name = f"{MULTI_INDEX_MODE_COLLECTION_PREFIX}_{filters['user_id']}"
            keys = self.tair_client.tvs_scan(
                collection_name,
                filter_str=filter_str,
                batch=limit,
            )
        else:
            # scan all collections
            collections = self.list_cols()
            keys = []
            for collection_name in collections:
                scan_results = self.tair_client.tvs_scan(
                    collection_name,
                    filter_str=filter_str,
                    batch=limit,
                )
                for key in scan_results:
                    keys.append(key)
        memory_ids = [key.decode() for key in keys]
        futures = [self.pool.submit(self._get_single_memory, memory_id) for memory_id in memory_ids]
        return [future.result() for future in futures]

    def reset(self) -> None:
        """Reset by delete the collection and recreate it."""
        logger.warning(f"Resetting index {self.collection_name} and all the user's vector index(if exists)...")
        self.delete_col()
        self.create_col(self.collection_name, self.embedding_model_dims, self.distance_method)
