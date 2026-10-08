import copy
import json
import logging
from datetime import datetime, timezone
from functools import reduce

import numpy as np
import redis
from redis.commands.search.query import Query
from redisvl.index import SearchIndex
from redisvl.query import TextQuery, VectorQuery
from redisvl.query.filter import Num, Tag, Text

from mem0.memory.utils import extract_json
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Operators that compare a field against a numeric bound, mapped to the redisvl
# Num filter method that expresses them. Tag/Text can only do equality-style
# matching, so range operators must go through Num.
_NUMERIC_OPERATORS = {
    "gt": lambda field, value: Num(field) > value,
    "gte": lambda field, value: Num(field) >= value,
    "lt": lambda field, value: Num(field) < value,
    "lte": lambda field, value: Num(field) <= value,
}


def _build_condition(key, value):
    """Translate one ``{key: value}`` filter entry into a redisvl FilterExpression.

    ``value`` may be a scalar (exact Tag match), a list (Tag OR-of-values, i.e.
    ``in``), or an operator dict such as ``{"gte": 18}`` or ``{"icontains": "x"}``.
    """
    if isinstance(value, list):
        return Tag(key) == value

    if isinstance(value, dict):
        conditions = []
        for op, op_value in value.items():
            if op == "eq":
                conditions.append(Tag(key) == op_value)
            elif op == "ne":
                conditions.append(Tag(key) != op_value)
            elif op == "in":
                conditions.append(Tag(key) == list(op_value))
            elif op == "nin":
                conditions.append(Tag(key) != list(op_value))
            elif op in ("contains", "icontains"):
                # Redis full-text search is case-insensitive, so contains and
                # icontains map to the same Text match.
                conditions.append(Text(key) % op_value)
            elif op in _NUMERIC_OPERATORS:
                conditions.append(_NUMERIC_OPERATORS[op](key, op_value))
            else:
                raise ValueError(f"Unsupported filter operator: {op}")
        return reduce(lambda x, y: x & y, conditions)

    return Tag(key) == value


def _build_filter_expression(filters):
    """Build a redisvl FilterExpression from mem0's universal filter dict.

    Supports scalar equality, list membership, per-field operator dicts
    (eq/ne/gt/gte/lt/lte/in/nin/contains/icontains) and a top-level ``$or``.
    ``None`` values are skipped so an all-``None`` filter matches everything.
    ``$not`` is not supported: redisvl cannot negate a compound expression, so
    it is rejected rather than silently ignored.
    """
    if not filters:
        return None

    conditions = []
    for key, value in filters.items():
        if key == "$or":
            or_conditions = [_build_filter_expression(sub) for sub in value]
            or_conditions = [c for c in or_conditions if c is not None]
            if or_conditions:
                conditions.append(reduce(lambda x, y: x | y, or_conditions))
            continue
        if key == "$not":
            raise ValueError("Redis vector store does not support the $not filter operator yet")
        if value is None:
            continue
        conditions.append(_build_condition(key, value))

    if not conditions:
        return None
    return reduce(lambda x, y: x & y, conditions)


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
        self.embedding_model_dims = embedding_model_dims
        index_schema = {
            "name": collection_name,
            "prefix": f"mem0:{collection_name}",
        }

        fields = copy.deepcopy(DEFAULT_FIELDS)
        fields[-1]["attrs"]["dims"] = embedding_model_dims

        self.schema = {"index": index_schema, "fields": fields}

        self.client = redis.Redis.from_url(redis_url)
        self.index = SearchIndex.from_dict(self.schema)
        self.index.set_client(self.client)
        self.index.create(overwrite=True)

    def create_col(self, name=None, vector_size=None, distance=None):
        """
        Create a new collection (index) in Redis.

        Args:
            name (str, optional): Name for the collection. Defaults to None, which uses the current collection_name.
            vector_size (int, optional): Size of the vector embeddings. Defaults to None, which uses the current embedding_model_dims.
            distance (str, optional): Distance metric to use. Defaults to None, which uses 'cosine'.

        Returns:
            The created index object.
        """
        # Use provided parameters or fall back to instance attributes
        collection_name = name or self.schema["index"]["name"]
        embedding_dims = vector_size or self.embedding_model_dims
        distance_metric = distance or "cosine"

        # Create a new schema with the specified parameters
        index_schema = {
            "name": collection_name,
            "prefix": f"mem0:{collection_name}",
        }

        # Deep-copy the default fields so mutating the nested vector attrs never
        # leaks into the module global or other instances.
        fields = copy.deepcopy(DEFAULT_FIELDS)
        fields[-1]["attrs"]["dims"] = embedding_dims
        fields[-1]["attrs"]["distance_metric"] = distance_metric

        # Create the schema
        schema = {"index": index_schema, "fields": fields}

        # Create the index
        index = SearchIndex.from_dict(schema)
        index.set_client(self.client)
        index.create(overwrite=True)

        # Update instance attributes if creating a new collection
        if name:
            self.schema = schema
            self.index = index

        return index

    def insert(self, vectors: list, payloads: list = None, ids: list = None):
        data = []
        for vector, payload, id in zip(vectors, payloads, ids):
            # Start with required fields
            created_at_str = payload.get("created_at")
            created_at_ts = int(datetime.fromisoformat(created_at_str).timestamp()) if created_at_str else 0
            entry = {
                "memory_id": id,
                "hash": payload.get("hash", ""),
                "memory": payload.get("data", ""),
                "created_at": created_at_ts,
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

    def search(self, query: str, vectors: list, top_k: int = 5, filters: dict = None):
        filter = _build_filter_expression(filters)

        v = VectorQuery(
            vector=np.array(vectors, dtype=np.float32).tobytes(),
            vector_field_name="embedding",
            return_fields=["memory_id", "hash", "agent_id", "run_id", "user_id", "memory", "metadata", "created_at"],
            filter_expression=filter,
            num_results=top_k,
        )

        results = self.index.query(v)

        return [
            MemoryResult(
                id=result["memory_id"],
                score=max(0.0, 1.0 - float(result["vector_distance"])),
                payload={
                    "hash": result["hash"],
                    "data": result["memory"],
                    "created_at": datetime.fromtimestamp(
                        int(result["created_at"]), tz=timezone.utc
                    ).isoformat(timespec="microseconds"),
                    **(
                        {
                            "updated_at": datetime.fromtimestamp(
                                int(result["updated_at"]), tz=timezone.utc
                            ).isoformat(timespec="microseconds")
                        }
                        if "updated_at" in result
                        else {}
                    ),
                    **{field: result[field] for field in ["agent_id", "run_id", "user_id"] if field in result},
                    **{k: v for k, v in json.loads(extract_json(result["metadata"])).items()},
                },
            )
            for result in results
        ]

    def keyword_search(self, query, top_k=5, filters=None):
        """
        Search for memories using BM25 keyword search on the memory field.

        Args:
            query (str): Search query text.
            top_k (int): Maximum number of results. Defaults to 5.
            filters (dict, optional): Filters to apply (user_id, agent_id, run_id).

        Returns:
            List[MemoryResult]: Search results.
        """
        filter_expression = _build_filter_expression(filters)

        t = TextQuery(
            text=query,
            text_field_name="memory",
            return_fields=["memory_id", "hash", "agent_id", "run_id", "user_id", "memory", "metadata", "created_at"],
            filter_expression=filter_expression,
            num_results=top_k,
        )

        results = self.index.query(t)

        return [
            MemoryResult(
                id=result["memory_id"],
                score=result.get("text_score", 1.0),
                payload={
                    "hash": result["hash"],
                    "data": result["memory"],
                    "created_at": datetime.fromtimestamp(
                        int(result["created_at"]), tz=timezone.utc
                    ).isoformat(timespec="microseconds"),
                    **(
                        {
                            "updated_at": datetime.fromtimestamp(
                                int(result["updated_at"]), tz=timezone.utc
                            ).isoformat(timespec="microseconds")
                        }
                        if "updated_at" in result
                        else {}
                    ),
                    **{field: result[field] for field in ["agent_id", "run_id", "user_id"] if field in result},
                    **{k: v for k, v in json.loads(extract_json(result["metadata"])).items()},
                },
            )
            for result in results
        ]

    def delete(self, vector_id):
        self.index.drop_keys(f"{self.schema['index']['prefix']}:{vector_id}")

    def update(self, vector_id=None, vector=None, payload=None):
        created_at_str = payload.get("created_at")
        created_at_ts = int(datetime.fromisoformat(created_at_str).timestamp()) if created_at_str else 0
        updated_at_str = payload.get("updated_at")
        updated_at_ts = int(datetime.fromisoformat(updated_at_str).timestamp()) if updated_at_str else 0
        data = {
            "memory_id": vector_id,
            "hash": payload.get("hash", ""),
            "memory": payload.get("data", ""),
            "created_at": created_at_ts,
            "updated_at": updated_at_ts,
        }

        # Only update embedding if vector is provided
        if vector is not None:
            data["embedding"] = np.array(vector, dtype=np.float32).tobytes()

        for field in ["agent_id", "run_id", "user_id"]:
            if field in payload:
                data[field] = payload[field]

        data["metadata"] = json.dumps({k: v for k, v in payload.items() if k not in excluded_keys})
        self.index.load(data=[data], keys=[f"{self.schema['index']['prefix']}:{vector_id}"], id_field="memory_id")

    def get(self, vector_id):
        result = self.index.fetch(vector_id)
        if result is None:
            return None
        payload = {
            "hash": result["hash"],
            "data": result["memory"],
            "created_at": datetime.fromtimestamp(int(result["created_at"]), tz=timezone.utc).isoformat(
                timespec="microseconds"
            ),
            **(
                {
                    "updated_at": datetime.fromtimestamp(
                        int(result["updated_at"]), tz=timezone.utc
                    ).isoformat(timespec="microseconds")
                }
                if "updated_at" in result
                else {}
            ),
            **{field: result[field] for field in ["agent_id", "run_id", "user_id"] if field in result},
            **{k: v for k, v in json.loads(extract_json(result["metadata"])).items()},
        }

        return MemoryResult(id=result["memory_id"], payload=payload)

    def list_cols(self):
        return self.index.listall()

    def delete_col(self):
        self.index.delete()

    def col_info(self, name):
        return self.index.info()

    def reset(self):
        """
        Reset the index by deleting and recreating it.
        """
        collection_name = self.schema["index"]["name"]
        logger.warning(f"Resetting index {collection_name}...")
        self.delete_col()

        self.index = SearchIndex.from_dict(self.schema)
        self.index.set_client(self.client)
        self.index.create(overwrite=True)

        # or use
        # self.create_col(collection_name, self.embedding_model_dims)

        # Recreate the index with the same parameters
        self.create_col(collection_name, self.embedding_model_dims)

    def list(self, filters: dict = None, top_k: int = None) -> list:
        """
        List all recent created memories from the vector store.
        """
        filter = _build_filter_expression(filters)
        query = Query(str(filter) if filter is not None else "*").sort_by("created_at", asc=False)
        if top_k is not None:
            query = query.paging(0, top_k)

        results = self.index.search(query)
        return [
            [
                MemoryResult(
                    id=result["memory_id"],
                    payload={
                        "hash": result["hash"],
                        "data": result["memory"],
                        "created_at": datetime.fromtimestamp(
                            int(result["created_at"]), tz=timezone.utc
                        ).isoformat(timespec="microseconds"),
                        **(
                            {
                                "updated_at": datetime.fromtimestamp(
                                    int(result["updated_at"]), tz=timezone.utc
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
                        **{k: v for k, v in json.loads(extract_json(result["metadata"])).items()},
                    },
                )
                for result in results.docs
            ]
        ]
