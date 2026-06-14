"""Oracle AI Vector Search vector store integration for mem0."""

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional
import re
import array
import uuid

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
METADATA_PATTERN = re.compile(r"[a-zA-Z0-9_\.\[\],\s\*]*")


def _validate_metadata_key(metadata_key: str) -> None:
    if not METADATA_PATTERN.fullmatch(metadata_key):
        raise ValueError(
            f"Invalid metadata key '{metadata_key}'. "
            "Only letters, numbers, underscores, nesting via '.', "
            "and array wildcards '[*]' are allowed."
        )


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
                raise Exception(
                    f"Oracle DB client driver version {oracledb.clientversion()} not \
                    supported, must be >=23.4 for vector support"
                )

        if isinstance(self.client, oracledb.Connection):
            db_version = tuple([int(v) for v in self.client.version.split(".")])
        else:
            with self.client.acquire() as conn:
                db_version = tuple([int(v) for v in conn.version.split(".")])

        if db_version < (23, 4):
            raise Exception(
                f"Oracle DB version {oracledb.__version__} not supported, \
                must be >=23.4 for vector support"
            )

        collections = self.list_cols()
        if self._catalog_name(self.collection_name) not in {self._catalog_name(name) for name in collections}:
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
        index_parameters = self.config.canonical_index_parameters()
        if not index_parameters:
            return ""

        parameters = [f"type {self.config.index_type}"]
        if self.config.index_type == "HNSW":
            if "neighbors" in index_parameters:
                parameters.append(f"neighbors {index_parameters['neighbors']}")
            if "efconstruction" in index_parameters:
                parameters.append(f"efconstruction {index_parameters['efconstruction']}")
        else:
            if "neighbor_partitions" in index_parameters:
                parameters.append(f"neighbor partitions {index_parameters['neighbor_partitions']}")
            if "samples_per_partition" in index_parameters:
                parameters.append(f"samples_per_partition {index_parameters['samples_per_partition']}")
            if "min_vectors_per_partition" in index_parameters:
                parameters.append(f"min_vectors_per_partition {index_parameters['min_vectors_per_partition']}")

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

        _ids = ids
        if not _ids:
            _ids = [str(uuid.uuid4()) for _ in vectors]

        data = []
        for vector, payload, _id in zip(vectors, payloads or [{}] * len(vectors), _ids):
            document = {"id": _id, "vector": array.array("f", vector), "payload": payload}
            data.append(document)

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
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using the vector search index.

        Args:
            query (str): Query string
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search.

        Returns:
            List[OutputData]: Search results.
        """
        filter_clause, params = self._build_filters(filters)

        distance_metric = self.config.distance_metric

        sql = (
            f"SELECT id, payload, VECTOR_DISTANCE(vector, :query_vec, {distance_metric}) distance "
            f"FROM {self.collection_name} {filter_clause} ORDER BY VECTOR_DISTANCE(vector, :query_vec, {distance_metric}) FETCH FIRST :limit ROWS ONLY"
        )

        with self._get_cursor() as cursor:
            cursor.execute(sql, query_vec=array.array("f", vectors), limit=limit, **params)
            rows = cursor.fetchall()

        return [
            OutputData(
                id=row[0],
                payload=self._load_payload(row[1]),
                score=float(row[2]),
            )
            for row in rows
        ]

    def _build_filters(self, filters: Optional[Dict[str, Any]]) -> tuple[str, Dict[str, Any]]:
        if not filters:
            return "", {}

        clauses: List[str] = []
        params: Dict[str, Any] = {}

        for idx, (key, value) in enumerate(filters.items()):
            _validate_metadata_key(key)
            param = f"f_{idx}"

            # Build JSON path like @."a"."b" or @."a"[*]."b"
            path_parts: List[str] = []
            for part in key.split("."):
                if part.endswith("[*]"):
                    base = part[:-3]
                    path_parts.append(f'."{base}"[*]')
                else:
                    path_parts.append(f'."{part}"')
            json_path = "".join(path_parts)

            # Use JSON_EXISTS with PASSING BY VALUE to preserve types
            clauses.append(f"JSON_EXISTS(payload, '$?(@{json_path} == ${param})' PASSING :{param} AS \"{param}\")")
            params[param] = value

        return ("WHERE " + " AND ".join(clauses), params)

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
            if vector is not None:
                cursor.setinputsizes(vector=oracledb.DB_TYPE_VECTOR)
                cursor.execute(
                    f"UPDATE {self.collection_name} SET vector = :vector WHERE id = :vector_id",
                    {"vector": array.array("f", vector), "vector_id": vector_id},
                )
            if payload is not None:
                cursor.setinputsizes(payload=oracledb.DB_TYPE_JSON)
                cursor.execute(
                    f"UPDATE {self.collection_name} SET payload = :payload WHERE id = :vector_id",
                    {"payload": payload, "vector_id": vector_id},
                )

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
        FROM user_tables
        WHERE table_name = :table_name
        """

        with self._get_cursor() as cursor:
            cursor.execute(
                sql,
                table_name=self.collection_name.replace('"', ""),
            )
            result = cursor.fetchone()

        return {"name": result[0], "count": result[1], "size": result[2]}

    def list(self, filters: Optional[Dict[str, Any]] = None, limit: Optional[int] = None) -> List[OutputData]:
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        filter_clause, params = self._build_filters(filters)

        limit_clause = ""
        if limit is not None:
            limit_clause = " FETCH FIRST :limit ROWS ONLY"
            params["limit"] = limit

        sql = f"SELECT id, payload FROM {self.collection_name} {filter_clause} {limit_clause}"

        with self._get_cursor() as cursor:
            cursor.execute(sql, **params)
            rows = cursor.fetchall()

        return [OutputData(id=row[0], score=None, payload=self._load_payload(row[1])) for row in rows]

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
