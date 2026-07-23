"""Oracle AI Vector Search vector store integration for mem0."""

import array
import json
import logging
import math
import re
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

try:
    import oracledb
except ImportError as exc:  # pragma: no cover - dependency guard
    raise ImportError("Oracle AI Vector Search requires the 'oracledb' package.") from exc

from pydantic import BaseModel

from mem0.configs.vector_stores.oracledb import OracleAIVectorSearchConfig
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    """Standard output structure returned from vector operations."""

    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict[str, Any]]


# Allow letters, digits, underscore, dot, brackets, comma, *, space (for 'to')
METADATA_PATTERN = re.compile(r"[a-zA-Z0-9_\.\[\],\s\*]+")


def _validate_metadata_key(metadata_key: str) -> None:
    if not METADATA_PATTERN.fullmatch(metadata_key):
        raise ValueError(
            f"Invalid metadata key '{metadata_key}'. "
            "Only letters, numbers, underscores, nesting via '.', "
            "and array wildcards '[*]' are allowed."
        )


_SCORE_FROM_DISTANCE = {
    "COSINE": lambda d: max(0.0, min(1.0, 1.0 - d)),
    "EUCLIDEAN": lambda d: 1.0 / (1.0 + max(0.0, d)),
    "EUCLIDEAN_SQUARED": lambda d: 1.0 / (1.0 + math.sqrt(max(0.0, d))),
    "HAMMING": lambda d: 1.0 / (1.0 + max(0.0, d)),
    "MANHATTAN": lambda d: 1.0 / (1.0 + max(0.0, d)),
    "DOT": lambda d: -d,
}


def _convert_distance_to_score(distance: float, metric: str) -> float:
    try:
        return _SCORE_FROM_DISTANCE[metric.upper()](distance)
    except KeyError:
        raise ValueError(f"Unsupported distance metric: {metric}") from None


_FIELD_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}
_COMPARISON_OPERATORS = {
    "eq": "==",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
}
_LOGICAL_OPERATORS = {
    "$and": "and",
    "$or": "or",
    "$not": "not",
    "AND": "and",
    "OR": "or",
    "NOT": "not",
}


def _json_path(metadata_key: str) -> str:
    _validate_metadata_key(metadata_key)

    path_parts: List[str] = []
    for part in metadata_key.split("."):
        if part.endswith("[*]"):
            path_parts.append(f'."{part[:-3]}"[*]')
        else:
            path_parts.append(f'."{part}"')
    return "".join(path_parts)


def _bind_filter_value(value: Any, params: Dict[str, Any]) -> tuple[str, str]:
    param = f"f_{len(params)}"
    params[param] = value
    return f"${param}", f':{param} AS "{param}"'


def _json_exists(json_path: str, predicate: str, passings: List[str]) -> str:
    passing_clause = f" PASSING {', '.join(passings)}" if passings else ""
    return f"JSON_EXISTS(payload, '${json_path}?({predicate})'{passing_clause})"


def _validate_scalar_operand(operator: str, value: Any) -> None:
    if isinstance(value, (dict, list, tuple, set)):
        raise ValueError(f"Oracle filter operator {operator!r} requires a scalar value")


def _build_field_condition(metadata_key: str, value: Any, params: Dict[str, Any]) -> str:
    json_path = _json_path(metadata_key)

    if value == "*":
        return f"JSON_EXISTS(payload, '${json_path}')"

    if not isinstance(value, dict):
        _validate_scalar_operand("eq", value)
        if value is None:
            return _json_exists(json_path, "@ == null", [])
        variable, passing = _bind_filter_value(value, params)
        return _json_exists(json_path, f"@ == {variable}", [passing])

    if not value:
        raise ValueError(f"Operator filter for field {metadata_key!r} must not be empty")

    unsupported = set(value) - _FIELD_OPERATORS
    if unsupported:
        raise ValueError(
            f"Unsupported Oracle filter operator(s) for field {metadata_key!r}: "
            f"{', '.join(sorted(map(str, unsupported)))}"
        )

    predicates: List[str] = []
    passings: List[str] = []
    additional_clauses: List[str] = []

    for operator, operand in value.items():
        if operator in _COMPARISON_OPERATORS:
            _validate_scalar_operand(operator, operand)
            if operand is None:
                if operator not in {"eq", "ne"}:
                    raise ValueError(f"Oracle filter operator {operator!r} does not support null")
                predicates.append(f"@ {_COMPARISON_OPERATORS[operator]} null")
                continue
            variable, passing = _bind_filter_value(operand, params)
            predicates.append(f"@ {_COMPARISON_OPERATORS[operator]} {variable}")
            passings.append(passing)
            continue

        if operator in {"in", "nin"}:
            if not isinstance(operand, (list, tuple)) or not operand:
                raise ValueError(f"Oracle filter operator {operator!r} requires a non-empty list")

            variables: List[str] = []
            list_passings: List[str] = []
            for item in operand:
                _validate_scalar_operand(operator, item)
                if item is None:
                    variables.append("null")
                    continue
                variable, passing = _bind_filter_value(item, params)
                variables.append(variable)
                list_passings.append(passing)

            membership = _json_exists(json_path, f"@ in ({', '.join(variables)})", list_passings)
            if operator == "in":
                additional_clauses.append(membership)
            else:
                additional_clauses.append(f"NOT ({membership})")
            continue

        if not isinstance(operand, str):
            raise ValueError(f"Oracle filter operator {operator!r} requires a string value")

        if operator == "contains":
            variable, passing = _bind_filter_value(operand, params)
            predicates.append(f"@ has substring {variable}")
            passings.append(passing)
        else:
            variable, passing = _bind_filter_value(operand.lower(), params)
            predicates.append(f"@.lower() has substring {variable}")
            passings.append(passing)

    clauses = list(additional_clauses)
    if predicates:
        clauses.insert(0, _json_exists(json_path, " && ".join(predicates), passings))

    if len(clauses) == 1:
        return clauses[0]
    return "(" + " AND ".join(clauses) + ")"


def _build_filter_group(filters: Dict[str, Any], params: Dict[str, Any]) -> str:
    if not isinstance(filters, dict) or not filters:
        raise ValueError("Oracle filter groups must be non-empty dictionaries")

    clauses: List[str] = []
    for key, value in filters.items():
        if key in _LOGICAL_OPERATORS:
            if not isinstance(value, list) or not value:
                raise ValueError(f"Logical filter operator {key!r} requires a non-empty list")

            nested = [_build_filter_group(condition, params) for condition in value]
            logical_operator = _LOGICAL_OPERATORS[key]
            if logical_operator == "not":
                clauses.append(f"NOT ({' OR '.join(nested)})")
            else:
                joiner = " AND " if logical_operator == "and" else " OR "
                clauses.append("(" + joiner.join(nested) + ")")
            continue

        if key.startswith("$"):
            raise ValueError(f"Unsupported Oracle logical filter operator: {key}")

        clauses.append(_build_field_condition(key, value, params))

    if len(clauses) == 1:
        return clauses[0]
    return "(" + " AND ".join(clauses) + ")"


class OracleAIVectorSearch(VectorStoreBase):
    """Oracle AI Vector Search backend for mem0."""

    def __init__(self, **kwargs: Any) -> None:
        self.config = OracleAIVectorSearchConfig(**kwargs)
        self.collection_name = self.config.collection_name

        if self.config.client:
            logger.debug("Using Oracle connection pool: %s", self.config.client)
            self.client = self.config.client
            self._owns_client = False
        elif self.config.use_connection_pool:
            pool_kwargs = {
                "min": 1,
                "max": 4,
            }
            pool_kwargs.update(self.config.connection_params)

            logger.debug("Creating Oracle connection pool")
            self.client = oracledb.create_pool(**pool_kwargs)
            self._owns_client = True
        else:
            logger.debug("Creating Oracle connection")
            self.client = oracledb.connect(**self.config.connection_params)
            self._owns_client = True

        if not (hasattr(self.client, "thin") and self.client.thin):
            if oracledb.clientversion()[:2] < (23, 4):
                raise RuntimeError(
                    f"Oracle DB client driver version {'.'.join(map(str, oracledb.clientversion()))} "
                    "not supported, must be >=23.4 for vector support"
                )

        if isinstance(self.client, oracledb.Connection):
            db_version = tuple([int(v) for v in self.client.version.split(".")])
        else:
            with self.client.acquire() as conn:
                db_version = tuple([int(v) for v in conn.version.split(".")])

        if db_version < (23, 4):
            raise ValueError(
                f"Oracle DB version {'.'.join(map(str, db_version))} not supported, must be >=23.4 for vector support"
            )

        self.create_col()

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        if isinstance(self.client, oracledb.ConnectionPool):
            with self.client.acquire() as connection:
                with connection.cursor() as cursor:
                    try:
                        yield cursor
                        if commit:
                            connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
        else:
            with self.client.cursor() as cursor:
                try:
                    yield cursor
                    if commit:
                        self.client.commit()
                except Exception:
                    self.client.rollback()
                    raise

    # Utility helpers --------------------------------------------------
    @staticmethod
    def _load_payload(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if hasattr(value, "read"):
            value = value.read()
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.debug("Failed to decode payload JSON")
            raise

    @staticmethod
    def _catalog_name(name: str) -> str:
        return name.replace('"', "")

    def _create_index_ddl(self) -> str:
        accuracy_str = ""
        if self.config.index_accuracy:
            accuracy_str = f"WITH TARGET ACCURACY {self.config.index_accuracy}"

        parameters = self._index_parameters()
        parameters_str = f"PARAMETERS ({parameters})" if parameters else ""

        distance_metric = self.config.distance_metric

        create_index = (
            f"CREATE VECTOR INDEX IF NOT EXISTS {self.config.index_name} ON {self.collection_name} (vector) "
            f"ORGANIZATION {'INMEMORY NEIGHBOR GRAPH' if self.config.index_type == 'HNSW' else 'NEIGHBOR PARTITIONS'}"
            f" DISTANCE {distance_metric} {accuracy_str} {parameters_str}"
        )

        return create_index

    def _index_parameters(self) -> str:
        index_parameters = self.config.index_parameters
        if not index_parameters:
            return ""

        parameters = [f"type {self.config.index_type}"]
        parameters.extend(f"{key} {value}" for key, value in index_parameters.items())

        return ", ".join(parameters)

    # Vector store API -------------------------------------------------
    def create_col(self) -> None:
        """
        Create a new collection (table in Oracle).
        Will also initialize vector search index if specified.
        """
        with self._get_cursor(commit=True) as cursor:
            cursor.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    id VARCHAR2(36) PRIMARY KEY,
                    vector VECTOR({self.config.embedding_model_dims}),
                    payload JSON
                )
                """
            )

            if self.config.do_create_index:
                ddl = self._create_index_ddl()
                cursor.execute(ddl)

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if payloads is not None and len(payloads) != len(vectors):
            raise ValueError(f"Payload count must match vector count. Expected {len(vectors)} got {len(payloads)}.")
        if ids is not None and len(ids) != len(vectors):
            raise ValueError(f"ID count must match vector count. Expected {len(vectors)} got {len(ids)}.")

        ids = ids or [str(uuid.uuid4()) for _ in vectors]
        data = [
            {"id": _id, "vector": array.array("f", vector), "payload": payload}
            for vector, payload, _id in zip(vectors, payloads or [{}] * len(vectors), ids)
        ]

        with self._get_cursor(commit=True) as cursor:
            cursor.setinputsizes(
                vector=oracledb.DB_TYPE_VECTOR,
                payload=oracledb.DB_TYPE_JSON,
            )
            cursor.executemany(
                f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES (:id, :vector, :payload)", data
            )

    def search(
        self,
        query: str,
        vectors: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using the vector search index.

        Args:
            query (str): Query string
            vectors (List[float]): Query vector.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """
        filter_clause, params = self._build_filters(filters)

        distance_metric = self.config.distance_metric

        sql = (
            f"SELECT id, payload, VECTOR_DISTANCE(vector, :query_vec, {distance_metric}) distance "
            f"FROM {self.collection_name} {filter_clause} ORDER BY distance FETCH APPROX FIRST :limit ROWS ONLY"
        )

        with self._get_cursor() as cursor:
            cursor.execute(sql, query_vec=array.array("f", vectors), limit=top_k, **params)
            rows = cursor.fetchall()

        return [
            OutputData(
                id=row[0],
                payload=self._load_payload(row[1]),
                score=_convert_distance_to_score(float(row[2]), distance_metric),
            )
            for row in rows
        ]

    def _build_filters(self, filters: Optional[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
        if not filters:
            return "", {}

        params: Dict[str, Any] = {}
        return "WHERE " + _build_filter_group(filters, params), params

    def delete(self, vector_id: str) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        with self._get_cursor(commit=True) as cursor:
            cursor.execute(f"DELETE FROM {self.collection_name} WHERE id = :id", id=vector_id)

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        if vector is None and payload is None:
            return

        with self._get_cursor(commit=True) as cursor:
            sets, params = [], {"vector_id": vector_id}
            if vector is not None:
                sets.append("vector = :vector")
                params["vector"] = array.array("f", vector)
                cursor.setinputsizes(vector=oracledb.DB_TYPE_VECTOR)
            if payload is not None:
                sets.append("payload = :payload")
                params["payload"] = payload
                cursor.setinputsizes(payload=oracledb.DB_TYPE_JSON)
            cursor.execute(f"UPDATE {self.collection_name} SET {', '.join(sets)} WHERE id = :vector_id", params)

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                f"SELECT id, payload FROM {self.collection_name} WHERE id = :vector_id",
                vector_id=vector_id,
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return OutputData(id=row[0], score=None, payload=self._load_payload(row[1]))

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        with self._get_cursor() as cursor:
            cursor.execute("SELECT table_name FROM user_tables")
            tables = [row[0] for row in cursor.fetchall()]
        return tables

    def delete_col(self) -> None:
        """Delete a collection."""
        with self._get_cursor(commit=True) as cursor:
            cursor.execute(f"DROP TABLE {self.collection_name} PURGE")

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        owner, table_name = self._split_collection_name()

        sql = f"""
        SELECT
            table_name,
            (SELECT COUNT(*) FROM {self.collection_name}) AS row_count,
            (SELECT
                ROUND(SUM(bytes) / 1024 / 1024, 2) || ' MB'
            FROM user_segments
            WHERE segment_name = :table_name
            AND segment_type = 'TABLE'
            ) AS total_size
        FROM all_tables
        WHERE table_name = :table_name
        AND owner = NVL(:owner, USER)
        """

        with self._get_cursor() as cursor:
            cursor.execute(sql, table_name=table_name, owner=owner)
            result = cursor.fetchone()

        if result is None:
            raise ValueError(f"Collection {self.collection_name} not found")

        return {"name": result[0], "count": result[1], "size": result[2]}

    def _split_collection_name(self) -> tuple[Optional[str], str]:
        """Split the quoted collection name into its optional owner and table parts."""
        segments = re.findall(r'"([^"]+)"', self.collection_name)
        if len(segments) > 1:
            return segments[-2], segments[-1]
        return None, segments[-1]

    def list(self, filters: Optional[Dict[str, Any]] = None, top_k: Optional[int] = 100) -> List[List[OutputData]]:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            top_k (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[List[OutputData]]: A single-element list holding the list of vectors.
        """
        filter_clause, params = self._build_filters(filters)

        limit_clause = ""
        if top_k is not None:
            limit_clause = " FETCH FIRST :limit ROWS ONLY"
            params["limit"] = top_k

        sql = f"SELECT id, payload FROM {self.collection_name} {filter_clause} {limit_clause}"

        with self._get_cursor() as cursor:
            cursor.execute(sql, **params)
            rows = cursor.fetchall()

        return [[OutputData(id=row[0], score=None, payload=self._load_payload(row[1])) for row in rows]]

    def reset(self) -> None:
        """Reset the index by deleting and recreating it."""
        logger.warning("Resetting collection %s", self.collection_name)
        self.delete_col()
        self.create_col()

    def __del__(self) -> None:
        """
        Close the database connection pool when the object is deleted.
        """
        try:
            if getattr(self, "_owns_client", False):
                self.client.close()
        except Exception:
            pass
