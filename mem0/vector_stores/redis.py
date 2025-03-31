import json
import logging
from datetime import datetime
from functools import reduce

import numpy as np
import pytz
import redis
from redis.commands.search.query import Query
from redisvl.index import SearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import Tag

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# TODO: Improve as these are not the best fields for the Redis's perspective. Might do away with them.
DEFAULT_FIELDS = [
    {"name": "memory_id", "type": "tag"},
    {"name": "hash", "type": "tag"},
    {"name": "agent_id", "type": "tag"},
    {"name": "run_id", "type": "tag"},
    {"name": "user_id", "type": "tag"},
    {"name": "memory", "type": "text"},
    {"name": "metadata", "type": "text"},
    # TODO: Although it is numeric but also accepts string
    {"name": "created_at", "type": "numeric"},
    {"name": "updated_at", "type": "numeric"},
    {
        "name": "embedding",
        "type": "vector",
        "attrs": {"distance_metric": "cosine", "algorithm": "flat", "datatype": "float32"},
    },
]

excluded_keys = {"user_id", "agent_id", "run_id", "hash", "data", "created_at", "updated_at"}


class MemoryResult:
    def __init__(self, id: str, payload: dict, score: float = None):
        self.id = id
        self.payload = payload
        self.score = score


class RedisDB(VectorStoreBase):
    def __init__(
        self,
        redis_url: str,
        collection_name: str,
        embedding_model_dims: int,
    ):
        """
        Initialize the Redis vector store.

        Args:
            redis_url (str): Redis URL.
            collection_name (str): Collection name.
            embedding_model_dims (int): Embedding model dimensions.
        """
        index_schema = {
            "name": collection_name,
            "prefix": f"mem0:{collection_name}",
        }

        fields = DEFAULT_FIELDS.copy()
        fields[-1]["attrs"]["dims"] = embedding_model_dims

        self.schema = {"index": index_schema, "fields": fields}

        self.client = redis.Redis.from_url(redis_url)
        self.index = SearchIndex.from_dict(self.schema)
        self.index.set_client(self.client)
        self.index.create(overwrite=True)

    # TODO: Implement multiindex support.
    def create_col(self, name, vector_size, distance):
        raise NotImplementedError("Collection/Index creation not supported yet.")

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        data = []
        for vector, payload, id in zip(vectors, payloads, ids):
            # Start with required fields
            entry = {
                "memory_id": id,
                "hash": payload["hash"],
                "memory": payload["data"],
                "created_at": int(datetime.fromisoformat(payload["created_at"]).timestamp()),
                "embedding": np.array(vector, dtype=np.float32).tobytes(),
            }

            # Conditionally add optional fields
            for field in ["agent_id", "run_id", "user_id"]:
                if field in payload:
                    entry[field] = payload[field]

            # Add metadata excluding specific keys
            entry["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})

            data.append(entry)
        self.index.load(data, id_field="memory_id")

    def search(self, query: str, vectors: list, limit: int = 5, filters: dict = None):
        conditions = [Tag(key) == value for key, value in filters.items() if value is not None]
        filter = reduce(lambda x, y: x & y, conditions)

        v = VectorQuery(
            vector=np.array(vectors, dtype=np.float32).tobytes(),
            vector_field_name="embedding",
            return_fields=["memory_id", "hash", "agent_id", "run_id", "user_id", "memory", "metadata", "created_at"],
            filter_expression=filter,
            num_results=limit,
        )

        results = self.index.query(v)

        return [
            MemoryResult(
                id=result["memory_id"],
                score=result["vector_distance"],
                payload={
                    "hash": result["hash"],
                    "data": result["memory"],
                    "created_at": datetime.fromtimestamp(
                        int(result["created_at"]), tz=pytz.timezone("US/Pacific")
                    ).isoformat(timespec="microseconds"),
                    **(
                        {
                            "updated_at": datetime.fromtimestamp(
                                int(result["updated_at"]), tz=pytz.timezone("US/Pacific")
                            ).isoformat(timespec="microseconds")
                        }
                        if "updated_at" in result
                        else {}
                    ),
                    **{field: result[field] for field in ["agent_id", "run_id", "user_id"] if field in result},
                    **{k: v for k, v in json.loads(result["metadata"]).items()},
                },
            )
            for result in results
        ]

    def delete(self, vector_id):
        self.index.drop_keys(f"{self.schema['index']['prefix']}:{vector_id}")

    def update(self, vector_id=None, vector=None, payload=None):
        data = {
            "memory_id": vector_id,
            "hash": payload["hash"],
            "memory": payload["data"],
            "created_at": int(datetime.fromisoformat(payload["created_at"]).timestamp()),
            "updated_at": int(datetime.fromisoformat(payload["updated_at"]).timestamp()),
            "embedding": np.array(vector, dtype=np.float32).tobytes(),
        }

        for field in ["agent_id", "run_id", "user_id"]:
            if field in payload:
                data[field] = payload[field]

        data["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})
        self.index.load(data=[data], keys=[f"{self.schema['index']['prefix']}:{vector_id}"], id_field="memory_id")

    def get(self, vector_id):
        result = self.index.fetch(vector_id)
        payload = {
            "hash": result["hash"],
            "data": result["memory"],
            "created_at": datetime.fromtimestamp(int(result["created_at"]), tz=pytz.timezone("US/Pacific")).isoformat(
                timespec="microseconds"
            ),
            **(
                {
                    "updated_at": datetime.fromtimestamp(
                        int(result["updated_at"]), tz=pytz.timezone("US/Pacific")
                    ).isoformat(timespec="microseconds")
                }
                if "updated_at" in result
                else {}
            ),
            **{field: result[field] for field in ["agent_id", "run_id", "user_id"] if field in result},
            **{k: v for k, v in json.loads(result["metadata"]).items()},
        }

        return MemoryResult(id=result["memory_id"], payload=payload)

    def list_cols(self):
        return self.index.listall()

    def delete_col(self):
        self.index.delete()

    def col_info(self, name):
        return self.index.info()

    def list(self, filters: dict = None, limit: int = None) -> list:
        """
        List all recent created memories from the vector store.
        """
        conditions = [Tag(key) == value for key, value in filters.items() if value is not None]
        filter = reduce(lambda x, y: x & y, conditions)
        query = Query(str(filter)).sort_by("created_at", asc=False)
        if limit is not None:
            query = Query(str(filter)).sort_by("created_at", asc=False).paging(0, limit)

        results = self.index.search(query)
        return [
            [
                MemoryResult(
                    id=result["memory_id"],
                    payload={
                        "hash": result["hash"],
                        "data": result["memory"],
                        "created_at": datetime.fromtimestamp(
                            int(result["created_at"]), tz=pytz.timezone("US/Pacific")
                        ).isoformat(timespec="microseconds"),
                        **(
                            {
                                "updated_at": datetime.fromtimestamp(
                                    int(result["updated_at"]), tz=pytz.timezone("US/Pacific")
                                ).isoformat(timespec="microseconds")
                            }
                            if result.__dict__.get("updated_at")
                            else {}
                        ),
                        **{
                            field: result[field]
                            for field in ["agent_id", "run_id", "user_id"]
                            if field in result.__dict__
                        },
                        **{k: v for k, v in json.loads(result["metadata"]).items()},
                    },
                )
                for result in results.docs
            ]
        ]
