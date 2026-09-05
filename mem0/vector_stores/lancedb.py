import json
import logging
import os
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import lancedb
    import pyarrow as pa
except ImportError:
    raise ImportError(
        "The 'lancedb' library is required. Please install it using "
        "'pip install \"mem0ai[vector-stores]\"' or 'pip install lancedb'."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_FILTER_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}
_LOGICAL_FILTER_ALIASES = {"AND": "$and", "OR": "$or", "NOT": "$not"}
_LOGICAL_FILTER_OPERATORS = {"$and", "$or", "$not"}


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict]


class LanceDB(VectorStoreBase):
    def __init__(
        self,
        collection_name: str = "mem0",
        path: Optional[str] = None,
        embedding_model_dims: int = 1536,
        distance: str = "cosine",
    ):
        self._validate_embedding_dimension(embedding_model_dims)
        self.collection_name = collection_name
        self.path = path or "/tmp/lancedb"
        self.embedding_model_dims = embedding_model_dims
        self.distance = distance

        os.makedirs(self.path, exist_ok=True)
        self.client = lancedb.connect(self.path)
        self.table = self.create_col(collection_name)

    def _schema(self, vector_size: Optional[int] = None):
        dimension = self.embedding_model_dims if vector_size is None else vector_size
        return pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("vector", pa.list_(pa.float32(), dimension)),
                pa.field("payload", pa.string()),
            ]
        )

    def _table_names(self) -> List[str]:
        list_tables = getattr(self.client, "list_tables", None)
        if callable(list_tables):
            names: List[str] = []
            page_token = None
            while True:
                response = list_tables(page_token=page_token)
                names.extend(getattr(response, "tables", response))
                page_token = getattr(response, "page_token", None)
                if not page_token:
                    return names

        table_names = self.client.table_names
        if not callable(table_names):
            return list(table_names)

        names: List[str] = []
        page_token = None
        page_size = 100
        while True:
            page = list(table_names(page_token=page_token, limit=page_size))
            names.extend(page)
            if len(page) < page_size:
                return names
            page_token = page[-1]

    @staticmethod
    def _escape_sql_string(value: str) -> str:
        return str(value).replace("'", "''")

    @classmethod
    def _id_where(cls, vector_id: str) -> str:
        return f"id = '{cls._escape_sql_string(vector_id)}'"

    @staticmethod
    def _dump_payload(payload: Optional[Dict]) -> str:
        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            raise TypeError("Payload must be a dictionary or None")
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    def _normalize_vector(self, vector: List[float]) -> List[float]:
        normalized = [float(value) for value in vector]
        if len(normalized) != self.embedding_model_dims:
            raise ValueError(
                f"Vector has dimension {len(normalized)}, but LanceDB collection {self.collection_name!r} "
                f"expects {self.embedding_model_dims}"
            )
        return normalized

    @staticmethod
    def _validate_top_k(top_k: int) -> None:
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 0:
            raise ValueError("top_k must be a non-negative integer")

    @staticmethod
    def _validate_embedding_dimension(dimension: int) -> None:
        if not isinstance(dimension, int) or dimension <= 0:
            raise ValueError("embedding_model_dims must be a positive integer")

    @staticmethod
    def _load_payload(payload: Optional[str]) -> Dict:
        if not payload:
            return {}
        try:
            loaded = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to decode LanceDB payload JSON")
            return {}
        if not isinstance(loaded, dict):
            logger.warning("LanceDB payload JSON must decode to a dictionary")
            return {}
        return loaded

    @staticmethod
    def _matches_filter_value(actual, expected) -> bool:
        if expected == "*":
            return True

        if isinstance(expected, list):
            return actual in expected

        if not isinstance(expected, dict):
            return actual == expected

        unsupported = set(expected) - _FILTER_OPERATORS
        if unsupported:
            raise ValueError(f"Unsupported filter operator(s): {sorted(unsupported)}")

        for operator, value in expected.items():
            try:
                if operator == "eq" and actual != value:
                    return False
                if operator == "ne" and actual == value:
                    return False
                if operator == "gt" and actual <= value:
                    return False
                if operator == "gte" and actual < value:
                    return False
                if operator == "lt" and actual >= value:
                    return False
                if operator == "lte" and actual > value:
                    return False
                if operator == "in" and actual not in value:
                    return False
                if operator == "nin" and actual in value:
                    return False
                if operator == "contains" and value not in actual:
                    return False
                if operator == "icontains" and str(value).lower() not in str(actual).lower():
                    return False
            except TypeError:
                return False

        return True

    @classmethod
    def _validate_filters(cls, filters: Dict) -> None:
        if not isinstance(filters, dict):
            raise ValueError("Filters must be a dictionary")

        for key, expected in filters.items():
            if not isinstance(key, str):
                raise ValueError("Filter field names must be strings")

            logical_key = _LOGICAL_FILTER_ALIASES.get(key, key)
            if logical_key in _LOGICAL_FILTER_OPERATORS:
                if not isinstance(expected, list) or not all(isinstance(item, dict) for item in expected):
                    raise ValueError(f"{logical_key} filter value must be a list of filter dictionaries")
                for item in expected:
                    cls._validate_filters(item)
                continue

            if key.startswith("$"):
                raise ValueError(f"Unsupported logical filter operator: {key}")

            if not isinstance(expected, dict):
                continue
            if not expected:
                raise ValueError(f"Operator filter for field {key!r} must not be empty")

            unsupported = set(expected) - _FILTER_OPERATORS
            if unsupported:
                raise ValueError(f"Unsupported filter operator(s): {sorted(unsupported)}")

            for operator, value in expected.items():
                if operator in {"eq", "ne", "gt", "gte", "lt", "lte"}:
                    if isinstance(value, (dict, list, tuple, set)):
                        raise ValueError(f"Filter operator {operator!r} requires a scalar value")
                    if operator in {"gt", "gte", "lt", "lte"} and value is None:
                        raise ValueError(f"Filter operator {operator!r} does not support null")
                    continue

                if operator in {"in", "nin"}:
                    if not isinstance(value, (list, tuple)) or not value:
                        raise ValueError(f"Filter operator {operator!r} requires a non-empty list")
                    if any(isinstance(item, (dict, list, tuple, set)) for item in value):
                        raise ValueError(f"Filter operator {operator!r} list items must be scalar values")
                    continue

                if not isinstance(value, str):
                    raise ValueError(f"Filter operator {operator!r} requires a string value")

    @classmethod
    def _apply_filters(cls, payload: Dict, filters: Optional[Dict]) -> bool:
        if not filters:
            return True

        for key, expected in filters.items():
            logical_key = _LOGICAL_FILTER_ALIASES.get(key, key)
            if logical_key in _LOGICAL_FILTER_OPERATORS:
                if not isinstance(expected, list) or not all(isinstance(item, dict) for item in expected):
                    raise ValueError(f"{logical_key} filter value must be a list of filter dictionaries")

                matches = [cls._apply_filters(payload, item) for item in expected]
                if logical_key == "$and" and not all(matches):
                    return False
                if logical_key == "$or" and not any(matches):
                    return False
                if logical_key == "$not" and any(matches):
                    return False
                continue

            if key.startswith("$"):
                raise ValueError(f"Unsupported logical filter operator: {key}")

            if key not in payload:
                return False

            if not cls._matches_filter_value(payload[key], expected):
                return False

        return True

    def _score_from_distance(self, raw_score: Optional[float]) -> Optional[float]:
        if raw_score is None:
            return None
        raw_score = float(raw_score)
        if self.distance == "dot":
            return 1.0 - raw_score
        if self.distance == "cosine":
            return max(0.0, 1.0 - raw_score)
        return 1.0 / (1.0 + raw_score)

    def _parse_row(self, row: Dict) -> OutputData:
        raw_score = row.get("_distance")
        return OutputData(
            id=row.get("id"),
            score=self._score_from_distance(raw_score),
            payload=self._load_payload(row.get("payload")),
        )

    def create_col(self, name: str, vector_size: Optional[int] = None, distance: Optional[str] = None):
        next_dimension = self.embedding_model_dims if vector_size is None else vector_size
        next_distance = self.distance if distance is None else distance
        self._validate_embedding_dimension(next_dimension)

        if name in self._table_names():
            table = self.client.open_table(name)
            existing_dimension = getattr(table.schema.field("vector").type, "list_size", None)
            if existing_dimension != next_dimension:
                raise ValueError(
                    f"LanceDB collection {name!r} uses embedding dimension {existing_dimension}, "
                    f"but requested {next_dimension}"
                )
        else:
            table = self.client.create_table(name, schema=self._schema(next_dimension))

        self.collection_name = name
        self.embedding_model_dims = next_dimension
        self.distance = next_distance
        self.table = table
        return table

    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]
        if payloads is None:
            payloads = [{} for _ in vectors]
        if len(vectors) != len(ids) or len(vectors) != len(payloads):
            raise ValueError("Vectors, payloads, and IDs must have the same length")

        rows = [
            {
                "id": vector_id,
                "vector": self._normalize_vector(vector),
                "payload": self._dump_payload(payload),
            }
            for vector_id, vector, payload in zip(ids, vectors, payloads)
        ]
        self.table.add(rows)
        logger.info("Inserted %s vectors into LanceDB table %s", len(rows), self.collection_name)

    def search(
        self, query: str, vectors: List[list], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        self._validate_top_k(top_k)
        if filters is not None:
            self._validate_filters(filters)
        if top_k == 0:
            return []

        query_vector = vectors[0] if vectors and isinstance(vectors[0], list) else vectors
        query_vector = self._normalize_vector(query_vector)
        if not filters:
            rows = self.table.search(query_vector).metric(self.distance).limit(top_k).to_list()
            return [self._parse_row(row) for row in rows]

        table_size = self.table.count_rows()
        if table_size == 0:
            return []

        # LanceDB 0.17 cannot query arbitrary fields inside the JSON payload.
        # Grow the vector recall window until enough filtered matches are found
        # so a selective filter cannot silently under-return top_k results.
        fetch_k = min(max(top_k * 5, 50), table_size)
        while True:
            rows = self.table.search(query_vector).metric(self.distance).limit(fetch_k).to_list()
            results: List[OutputData] = []
            for row in rows:
                parsed = self._parse_row(row)
                if self._apply_filters(parsed.payload or {}, filters):
                    results.append(parsed)
                    if len(results) >= top_k:
                        break

            if len(results) >= top_k or fetch_k >= table_size:
                return results[:top_k]

            fetch_k = min(fetch_k * 2, table_size)

    def delete(self, vector_id: str):
        self.table.delete(self._id_where(vector_id))

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        existing = self.get(vector_id)
        if existing is None:
            return

        values = {}
        if vector is not None:
            values["vector"] = self._normalize_vector(vector)
        if payload is not None:
            values["payload"] = self._dump_payload(payload)
        if not values:
            return

        self.table.update(where=self._id_where(vector_id), values=values)

    def get(self, vector_id: str) -> Optional[OutputData]:
        rows = self.table.search().where(self._id_where(vector_id)).limit(1).to_list()
        return self._parse_row(rows[0]) if rows else None

    def list_cols(self) -> List[str]:
        return self._table_names()

    def delete_col(self):
        if self.collection_name in self._table_names():
            self.client.drop_table(self.collection_name)
        self.table = None

    def col_info(self) -> Dict:
        count = self.table.count_rows() if self.table is not None else 0
        return {
            "name": self.collection_name,
            "count": count,
            "dimension": self.embedding_model_dims,
            "distance": self.distance,
        }

    def list(self, filters: Optional[Dict] = None, top_k: int = 100) -> List[List[OutputData]]:
        self._validate_top_k(top_k)
        if filters is not None:
            self._validate_filters(filters)
        if top_k == 0:
            return [[]]

        rows = self.table.to_arrow().to_pylist()
        results: List[OutputData] = []
        for row in rows:
            parsed = self._parse_row(row)
            if filters and not self._apply_filters(parsed.payload or {}, filters):
                continue
            results.append(parsed)
            if len(results) >= top_k:
                break
        return [results]

    def reset(self):
        logger.warning("Resetting LanceDB table %s...", self.collection_name)
        self.table = self.client.create_table(self.collection_name, schema=self._schema(), mode="overwrite")
