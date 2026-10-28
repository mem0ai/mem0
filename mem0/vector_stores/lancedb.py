import json
import logging
import math
import os
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel

try:
    import lancedb
    import pyarrow as pa
except ImportError:
    raise ImportError(
        "LanceDB >= 0.40.0 and PyArrow >= 19.0.0 are required. "
        "Install them with 'pip install \"mem0ai[vector-stores]\"'."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


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
        if not hasattr(pa, "json_"):
            raise ImportError("LanceDB native JSON requires PyArrow >= 19.0.0; please upgrade PyArrow.")
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
                pa.field("payload", pa.json_()),
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

    @classmethod
    def _validate_json_numbers(cls, value):
        if isinstance(value, int) and not isinstance(value, bool) and not -(2**63) <= value < 2**64:
            raise ValueError("JSON integer outside lossless LanceDB range")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        if isinstance(value, dict):
            for item in value.values():
                cls._validate_json_numbers(item)
        elif isinstance(value, (list, tuple)):
            for item in value:
                cls._validate_json_numbers(item)

    @classmethod
    def _dump_payload(cls, payload: Optional[Dict]) -> str:
        if payload is None:
            payload = {}
        elif not isinstance(payload, dict):
            raise TypeError("Payload must be a dictionary or None")
        cls._validate_json_numbers(payload)
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)

    def _rows_for_write(self, rows):
        return pa.Table.from_pylist(rows, schema=self._schema())

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
        if not isinstance(dimension, int) or isinstance(dimension, bool) or dimension <= 0:
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
    def _literal(value):
        if not isinstance(value, str) or "\x00" in value:
            raise ValueError("Invalid filter string")
        return "'" + value.replace("'", "''") + "'"

    @classmethod
    def _path(cls, field):
        if not isinstance(field, str) or not field or "\x00" in field:
            raise ValueError("Invalid filter field")
        return "$[" + json.dumps(field, ensure_ascii=False) + "]"

    @classmethod
    def _safe_string(cls, field, raw):
        # Containers make json_get_string raise; a NULL key prevents that cast.
        key = cls._literal(field)
        return (
            f"json_get_string(payload, substr({key}, 1, length({key}) * "
            f"cast(nullif(starts_with({raw}, '\"'), false) AS int)))"
        )

    @classmethod
    def _scalar_equal(cls, field, value):
        path = cls._literal(cls._path(field))
        raw = f"json_extract(payload, {path})"
        if value is None:
            return f"COALESCE({raw} = 'null', false)"
        if isinstance(value, str):
            encoded = cls._literal(json.dumps(value, ensure_ascii=False, separators=(",", ":")))
            return f"COALESCE({raw} = {encoded}, false)"
        if isinstance(value, bool):
            return f"COALESCE({raw} = '{str(value).lower()}', false)"
        if isinstance(value, (int, float)) and abs(value) < 2**53 and math.isfinite(value):
            return f"COALESCE((regexp_like({raw}, '^-?[0-9]') AND try_cast({raw} AS DOUBLE) = {value!r}), false)"
        raise ValueError("Unsupported scalar filter value")

    @classmethod
    def _filter_sql(cls, filters):
        if not isinstance(filters, dict):
            raise ValueError("Filters must be a dictionary")
        expressions = []
        aliases = {"AND": "$and", "OR": "$or", "NOT": "$not"}
        for field, expected in filters.items():
            if not isinstance(field, str):
                raise ValueError("Filter field names must be strings")
            op = aliases.get(field, field)
            if op in ("$and", "$or", "$not"):
                if not isinstance(expected, list) or not all(isinstance(x, dict) for x in expected):
                    raise ValueError("Logical filter requires a list of dictionaries")
                children = [f"({cls._filter_sql(x)})" for x in expected]
                joined = (" AND " if op == "$and" else " OR ").join(children)
                joined = joined or ("true" if op == "$and" else "false")
                expressions.append(f"NOT ({joined})" if op == "$not" else f"({joined})")
                continue
            if field.startswith("$"):
                raise ValueError("Unsupported logical filter")
            path_literal = cls._literal(cls._path(field))
            raw = f"json_extract(payload, {path_literal})"
            exists = f"COALESCE(json_exists(payload, {path_literal}), false)"
            if expected == "*":
                expressions.append(exists)
                continue
            if isinstance(expected, list) and not expected:
                expressions.append("false")
                continue
            if isinstance(expected, dict):
                operators = expected
            elif isinstance(expected, list):
                operators = {"in": expected}
            else:
                operators = {"eq": expected}
            if not operators:
                raise ValueError("Empty operator filter")
            clauses = []
            for operator, value in operators.items():
                if operator in ("eq", "ne"):
                    eq = cls._scalar_equal(field, value)
                    clauses.append(eq if operator == "eq" else f"NOT ({eq})")
                elif operator in ("in", "nin"):
                    if not isinstance(value, (list, tuple)) or not value:
                        raise ValueError("in/nin require non-empty lists")
                    joined = " OR ".join(cls._scalar_equal(field, x) for x in value)
                    clauses.append(f"NOT ({joined})" if operator == "nin" else f"({joined})")
                elif operator in ("gt", "gte", "lt", "lte"):
                    symbol = {"gt": ">", "gte": ">=", "lt": "<", "lte": "<="}[operator]
                    if isinstance(value, str):
                        text = cls._safe_string(field, raw)
                        expr = f"{text} {symbol} {cls._literal(value)}"
                    elif (
                        isinstance(value, (int, float))
                        and not isinstance(value, bool)
                        and abs(value) < 2**53
                        and math.isfinite(value)
                    ):
                        expr = f"regexp_like({raw}, '^-?[0-9]') AND try_cast({raw} AS DOUBLE) {symbol} {value!r}"
                    else:
                        raise ValueError("Unsupported comparison value")
                    clauses.append(f"COALESCE(({expr}), false)")
                elif operator in ("contains", "icontains"):
                    if not isinstance(value, str):
                        raise ValueError("contains requires a string")
                    text = cls._safe_string(field, raw)
                    if operator == "icontains":
                        expr = f"starts_with({raw}, '\"') AND strpos(lower({text}), {cls._literal(value.lower())}) > 0"
                    else:
                        encoded = cls._literal(json.dumps(value, ensure_ascii=False))
                        key = cls._literal(field)
                        expr = (
                            f"(starts_with({raw}, '\"') AND strpos({text}, {cls._literal(value)}) > 0) OR "
                            f"(starts_with({raw}, '[') AND json_array_contains(payload, {path_literal}, {encoded})) OR "
                            f"(starts_with({raw}, '{{') AND "
                            f"json_get(json_get(payload, {key}), {cls._literal(value)}) IS NOT NULL)"
                        )
                    clauses.append(f"COALESCE(({expr}), false)")
                else:
                    raise ValueError(f"Unsupported filter operator: {operator}")
            expressions.append(f"({exists} AND {' AND '.join(clauses)})")
        return " AND ".join(expressions) or "true"

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
            schema = table.schema
            if "payload" not in schema.names or not (
                schema.field("payload").type == pa.large_binary()
                and (schema.field("payload").metadata or {}).get(b"ARROW:extension:name") == b"lance.json"
            ):
                raise ValueError(
                    f"LanceDB collection {name!r} has an incompatible payload schema. "
                    "Back up and export the old table, then import its rows into a new collection."
                )
            if "id" not in schema.names or schema.field("id").type != pa.string() or "vector" not in schema.names:
                raise ValueError(f"LanceDB collection {name!r} has an incompatible schema")
            existing_dimension = getattr(schema.field("vector").type, "list_size", None)
            if existing_dimension != next_dimension:
                raise ValueError(
                    f"LanceDB collection {name!r} uses embedding dimension {existing_dimension}, "
                    f"but requested {next_dimension}"
                )
            if schema.field("vector").type != pa.list_(pa.float32(), next_dimension):
                raise ValueError(f"LanceDB collection {name!r} has an incompatible vector schema")
        else:
            table = self.client.create_table(
                name, schema=self._schema(next_dimension), storage_options={"new_table_data_storage_version": "2.2"}
            )

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
        if rows:
            self.table.add(self._rows_for_write(rows))
        logger.info("Inserted %s vectors into LanceDB table %s", len(rows), self.collection_name)

    def search(
        self, query: str, vectors: List[list], top_k: int = 5, filters: Optional[Dict] = None
    ) -> List[OutputData]:
        self._validate_top_k(top_k)
        condition = self._filter_sql(filters) if filters is not None else None
        if top_k == 0:
            return []
        query_vector = vectors[0] if vectors and isinstance(vectors[0], list) else vectors
        query_vector = self._normalize_vector(query_vector)
        query_builder = self.table.search(query_vector).metric(self.distance)
        if condition is not None:
            query_builder = query_builder.where(condition, prefilter=True)
        return [self._parse_row(row) for row in query_builder.limit(top_k).to_list()]

    def delete(self, vector_id: str):
        self.table.delete(self._id_where(vector_id))

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        rows = self.table.search().where(self._id_where(vector_id)).limit(1).to_list()
        if not rows or (vector is None and payload is None):
            return
        row = rows[0]
        new_vector = self._normalize_vector(vector) if vector is not None else row["vector"]
        new_payload = self._dump_payload(payload) if payload is not None else row["payload"]
        batch = self._rows_for_write([{"id": row["id"], "vector": new_vector, "payload": new_payload}])
        self.table.merge_insert("id").when_matched_update_all().execute(batch)

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
        condition = self._filter_sql(filters) if filters is not None else None
        if top_k == 0:
            return [[]]
        query = self.table.search()
        if condition is not None:
            query = query.where(condition)
        return [[self._parse_row(row) for row in query.limit(top_k).to_list()]]

    def reset(self):
        logger.warning("Resetting LanceDB table %s...", self.collection_name)
        self.table = self.client.create_table(
            self.collection_name,
            schema=self._schema(),
            mode="overwrite",
            storage_options={"new_table_data_storage_version": "2.2"},
        )
