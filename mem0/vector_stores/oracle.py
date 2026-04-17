import array
import json
import logging
import re
import uuid
from contextlib import contextmanager
from typing import Any, List, Optional, Sequence

from pydantic import BaseModel

try:
    import oracledb
except ImportError as exc:
    raise ImportError(
        "The Oracle vector store requires the 'oracledb' package. "
        "Install it with `pip install oracledb` or `pip install mem0ai[vector_stores]`."
    ) from exc

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_$#]{0,127}$")
_JSON_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$")
_SUPPORTED_DISTANCES = {
    "COSINE",
    "DOT",
    "EUCLIDEAN",
    "EUCLIDEAN_SQUARED",
    "HAMMING",
    "MANHATTAN",
}
_DISTANCE_ALIASES = {"L2_SQUARED": "EUCLIDEAN_SQUARED"}
_VECTOR_FORMAT_TO_ARRAY_TYPE = {"FLOAT32": "f", "FLOAT64": "d"}
_FILTER_COLUMN_MAP = {"user_id": "USER_ID", "agent_id": "AGENT_ID", "run_id": "RUN_ID"}


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class OracleDB(VectorStoreBase):
    """Oracle AI Database vector store using native Oracle AI Vector Search.

    The provider stores embeddings in a native Oracle `VECTOR` column, searches with
    `VECTOR_DISTANCE`, and can create HNSW or IVF vector indexes with target accuracy.
    """

    def __init__(
        self,
        dsn: Optional[str] = None,
        collection_name: str = "mem0",
        embedding_model_dims: int = 1536,
        user: Optional[str] = None,
        password: Optional[str] = None,
        vector_format: str = "FLOAT32",
        distance: str = "COSINE",
        search_mode: str = "approx",
        target_accuracy: int = 90,
        auto_create: bool = True,
        index: Optional[dict] = None,
        minconn: int = 1,
        maxconn: int = 5,
        increment: int = 1,
        connection_pool: Optional[Any] = None,
        config_dir: Optional[str] = None,
        wallet_location: Optional[str] = None,
        wallet_password: Optional[str] = None,
        thick_mode: bool = False,
        lib_dir: Optional[str] = None,
        pool_kwargs: Optional[dict] = None,
    ):
        """Initialize the Oracle AI Database vector store.

        Args:
            dsn: Oracle Database DSN, for example `localhost:1521/FREEPDB1`.
            collection_name: Oracle table name that stores vectors and payloads.
            embedding_model_dims: Embedding vector dimension.
            user: Oracle Database user.
            password: Oracle Database password.
            vector_format: Oracle VECTOR storage format. Supported: FLOAT32, FLOAT64.
            distance: VECTOR_DISTANCE metric. Supported: COSINE, DOT, EUCLIDEAN,
                EUCLIDEAN_SQUARED, HAMMING, MANHATTAN.
            search_mode: `approx`, `exact`, or `auto`.
            target_accuracy: Query-time target accuracy for approximate search.
            auto_create: Whether to create the table and indexes automatically.
            index: Optional HNSW or IVF index configuration.
            connection_pool: Existing oracledb connection pool.
        """
        self.collection_name = self._validate_identifier(collection_name)
        self.embedding_model_dims = int(embedding_model_dims)
        self.vector_format = self._validate_vector_format(vector_format)
        self.distance = self._validate_distance(distance)
        self.search_mode = self._validate_search_mode(search_mode)
        self.target_accuracy = self._validate_accuracy(target_accuracy)
        self.index = self._normalize_index_config(index)
        self._owns_pool = connection_pool is None

        if thick_mode:
            if lib_dir:
                oracledb.init_oracle_client(lib_dir=lib_dir)
            else:
                oracledb.init_oracle_client()

        if connection_pool is not None:
            self.connection_pool = connection_pool
        else:
            pool_args = {
                "user": user,
                "password": password,
                "dsn": dsn,
                "min": minconn,
                "max": maxconn,
                "increment": increment,
            }
            if config_dir:
                pool_args["config_dir"] = config_dir
            if wallet_location:
                pool_args["wallet_location"] = wallet_location
            if wallet_password:
                pool_args["wallet_password"] = wallet_password
            if pool_kwargs:
                pool_args.update(pool_kwargs)
            self.connection_pool = oracledb.create_pool(**pool_args)

        if auto_create:
            self.create_col()

    @staticmethod
    def _validate_identifier(identifier: str) -> str:
        if not identifier or not _IDENTIFIER_RE.fullmatch(identifier):
            raise ValueError(
                "Oracle identifiers must start with a letter and contain only letters, numbers, _, $, or #."
            )
        return identifier.upper()

    @staticmethod
    def _validate_accuracy(value: int) -> int:
        value = int(value)
        if value < 1 or value > 100:
            raise ValueError("target_accuracy must be between 1 and 100.")
        return value

    @staticmethod
    def _validate_distance(distance: str) -> str:
        normalized = _DISTANCE_ALIASES.get(str(distance).upper(), str(distance).upper())
        if normalized not in _SUPPORTED_DISTANCES:
            raise ValueError(f"Unsupported Oracle vector distance metric: {distance}")
        return normalized

    @staticmethod
    def _validate_search_mode(search_mode: str) -> str:
        normalized = str(search_mode).lower()
        if normalized not in {"approx", "exact", "auto"}:
            raise ValueError("search_mode must be one of: approx, exact, auto")
        return normalized

    @staticmethod
    def _validate_vector_format(vector_format: str) -> str:
        normalized = str(vector_format).upper()
        if normalized not in _VECTOR_FORMAT_TO_ARRAY_TYPE:
            raise ValueError("vector_format must be one of: FLOAT32, FLOAT64")
        return normalized

    def _normalize_index_config(self, index: Optional[dict]) -> dict:
        if index is None:
            index = {"create": True, "type": "hnsw"}
        elif hasattr(index, "model_dump"):
            index = index.model_dump()
        else:
            index = dict(index)

        normalized = {
            "create": True,
            "type": "hnsw",
            "target_accuracy": self.target_accuracy,
            "neighbors": 40,
            "efconstruction": 500,
            "neighbor_partitions": 100,
            "parallel": None,
        }
        normalized.update(index)
        normalized["type"] = str(normalized["type"]).lower()
        normalized["target_accuracy"] = self._validate_accuracy(normalized["target_accuracy"])

        if normalized["type"] not in {"hnsw", "ivf"}:
            raise ValueError("Oracle vector index type must be one of: hnsw, ivf")

        return normalized

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        """Get an Oracle cursor from the connection pool and manage commit/rollback."""
        conn = self.connection_pool.acquire()
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception:
            conn.rollback()
            logger.error("Error in Oracle cursor context", exc_info=True)
            raise
        finally:
            cur.close()
            self.connection_pool.release(conn)

    def _table_exists(self, cur) -> bool:
        cur.execute("SELECT table_name FROM user_tables WHERE table_name = :table_name", {"table_name": self.collection_name})
        return cur.fetchone() is not None

    def _index_exists(self, cur, index_name: str) -> bool:
        cur.execute("SELECT index_name FROM user_indexes WHERE index_name = :index_name", {"index_name": index_name})
        return cur.fetchone() is not None

    def _metadata_index_name(self, column_name: str) -> str:
        return self._validate_identifier(f"{self.collection_name}_{column_name}_IDX"[:128])

    def _vector_index_name(self) -> str:
        index_type = str(self.index["type"]).upper()
        return self._validate_identifier(f"{self.collection_name}_{index_type}_IDX"[:128])

    def _to_vector_bind(self, vector: Sequence[float]) -> array.array:
        if isinstance(vector, array.array):
            return vector
        array_type = _VECTOR_FORMAT_TO_ARRAY_TYPE[self.vector_format]
        return array.array(array_type, vector)

    @staticmethod
    def _payload_to_json(payload: Optional[dict]) -> str:
        return json.dumps(payload or {})

    @staticmethod
    def _payload_from_db(payload: Any) -> Optional[dict]:
        if payload is None:
            return None
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8")
        if isinstance(payload, str):
            return json.loads(payload)
        return payload

    @staticmethod
    def _payload_value(payload: Optional[dict], key: str) -> Optional[str]:
        if not payload:
            return None
        value = payload.get(key)
        if value is None:
            return None
        return str(value)

    def _create_metadata_indexes(self, cur) -> None:
        for column in ("USER_ID", "AGENT_ID", "RUN_ID"):
            index_name = self._metadata_index_name(column)
            if not self._index_exists(cur, index_name):
                cur.execute(f"CREATE INDEX {index_name} ON {self.collection_name} ({column})")

    def _create_vector_index(self, cur) -> None:
        if not self.index.get("create", True):
            return

        index_name = self._vector_index_name()
        if self._index_exists(cur, index_name):
            return

        accuracy = self._validate_accuracy(self.index["target_accuracy"])
        parallel = self.index.get("parallel")
        parallel_clause = f" PARALLEL {int(parallel)}" if parallel else ""

        if self.index["type"] == "hnsw":
            neighbors = int(self.index.get("neighbors", 40))
            efconstruction = int(self.index.get("efconstruction", 500))
            cur.execute(
                f"""
                CREATE VECTOR INDEX {index_name}
                ON {self.collection_name} (EMBEDDING)
                ORGANIZATION INMEMORY NEIGHBOR GRAPH
                DISTANCE {self.distance}
                WITH TARGET ACCURACY {accuracy}
                PARAMETERS (TYPE HNSW, NEIGHBORS {neighbors}, EFCONSTRUCTION {efconstruction}){parallel_clause}
                """
            )
            return

        neighbor_partitions = int(self.index.get("neighbor_partitions", 100))
        cur.execute(
            f"""
            CREATE VECTOR INDEX {index_name}
            ON {self.collection_name} (EMBEDDING)
            ORGANIZATION NEIGHBOR PARTITIONS
            DISTANCE {self.distance}
            WITH TARGET ACCURACY {accuracy}
            PARAMETERS (TYPE IVF, NEIGHBOR PARTITIONS {neighbor_partitions}){parallel_clause}
            """
        )

    def create_col(self) -> None:
        """Create the Oracle table and optional AI Vector Search index."""
        with self._get_cursor(commit=True) as cur:
            if not self._table_exists(cur):
                cur.execute(
                    f"""
                    CREATE TABLE {self.collection_name} (
                        ID VARCHAR2(128) PRIMARY KEY,
                        EMBEDDING VECTOR({self.embedding_model_dims}, {self.vector_format}),
                        PAYLOAD JSON,
                        USER_ID VARCHAR2(255),
                        AGENT_ID VARCHAR2(255),
                        RUN_ID VARCHAR2(255),
                        CREATED_AT TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UPDATED_AT TIMESTAMP
                    )
                    """
                )
            self._create_metadata_indexes(cur)
            self._create_vector_index(cur)

    def insert(self, vectors: list[list[float]], payloads=None, ids=None) -> None:
        """Insert vectors and payloads into Oracle AI Database."""
        logger.info(f"Inserting {len(vectors)} vectors into Oracle collection {self.collection_name}")
        payloads = payloads or [{} for _ in vectors]
        ids = ids or [str(uuid.uuid4()) for _ in vectors]

        data = []
        for vector_id, vector, payload in zip(ids, vectors, payloads):
            data.append(
                (
                    vector_id,
                    self._to_vector_bind(vector),
                    self._payload_to_json(payload),
                    self._payload_value(payload, "user_id"),
                    self._payload_value(payload, "agent_id"),
                    self._payload_value(payload, "run_id"),
                )
            )

        with self._get_cursor(commit=True) as cur:
            cur.executemany(
                f"""
                INSERT INTO {self.collection_name} (ID, EMBEDDING, PAYLOAD, USER_ID, AGENT_ID, RUN_ID)
                VALUES (:1, :2, :3, :4, :5, :6)
                """,
                data,
            )

    def _build_filter_clause(self, filters: Optional[dict]) -> tuple[str, dict]:
        conditions = []
        params = {}

        if not filters:
            return "", params

        for idx, (key, value) in enumerate(filters.items()):
            param_name = f"filter_{idx}"
            if key in _FILTER_COLUMN_MAP:
                conditions.append(f"{_FILTER_COLUMN_MAP[key]} = :{param_name}")
                params[param_name] = str(value)
                continue

            json_path = key.removeprefix("metadata.") if key.startswith("metadata.") else key
            if not _JSON_PATH_RE.fullmatch(json_path):
                raise ValueError(f"Unsupported Oracle JSON filter path: {key}")
            conditions.append(f"JSON_VALUE(PAYLOAD, '$.{json_path}') = :{param_name}")
            params[param_name] = str(value)

        return "WHERE " + " AND ".join(conditions), params

    def _fetch_clause(self, top_k: int) -> str:
        top_k = int(top_k)
        if top_k < 1:
            raise ValueError("top_k must be greater than zero.")

        if self.search_mode == "exact":
            return f"FETCH EXACT FIRST {top_k} ROWS ONLY"
        if self.search_mode == "approx":
            return f"FETCH APPROX FIRST {top_k} ROWS ONLY WITH TARGET ACCURACY {self.target_accuracy}"
        return f"FETCH FIRST {top_k} ROWS ONLY"

    def search(
        self,
        query: str,
        vectors: list[float],
        top_k: Optional[int] = 5,
        filters: Optional[dict] = None,
    ) -> List[OutputData]:
        """Search similar vectors using Oracle VECTOR_DISTANCE.

        Args:
            query: Original text query. The Oracle provider receives the embedded vector from Mem0.
            vectors: Query embedding vector.
            top_k: Number of nearest vectors to return.
            filters: Optional metadata filters pushed down to Oracle SQL.
        """
        filter_clause, params = self._build_filter_clause(filters)
        params["query_vector"] = self._to_vector_bind(vectors)
        distance_expr = f"VECTOR_DISTANCE(EMBEDDING, :query_vector, {self.distance})"

        sql = f"""
            SELECT ID, {distance_expr} AS DISTANCE, PAYLOAD
            FROM {self.collection_name}
            {filter_clause}
            ORDER BY {distance_expr}
            {self._fetch_clause(top_k or 5)}
        """

        with self._get_cursor() as cur:
            cur.execute(sql, params)
            results = cur.fetchall()

        return [
            OutputData(id=str(row[0]), score=float(row[1]), payload=self._payload_from_db(row[2])) for row in results
        ]

    def delete(self, vector_id: str) -> None:
        """Delete a vector by ID."""
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DELETE FROM {self.collection_name} WHERE ID = :vector_id", {"vector_id": vector_id})

    def update(
        self,
        vector_id: str,
        vector: Optional[list[float]] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """Update a vector and/or payload by ID."""
        set_clauses = []
        params = {"vector_id": vector_id}

        if vector is not None:
            set_clauses.append("EMBEDDING = :embedding")
            params["embedding"] = self._to_vector_bind(vector)

        if payload is not None:
            set_clauses.extend(
                [
                    "PAYLOAD = :payload",
                    "USER_ID = :user_id",
                    "AGENT_ID = :agent_id",
                    "RUN_ID = :run_id",
                ]
            )
            params["payload"] = self._payload_to_json(payload)
            params["user_id"] = self._payload_value(payload, "user_id")
            params["agent_id"] = self._payload_value(payload, "agent_id")
            params["run_id"] = self._payload_value(payload, "run_id")

        if not set_clauses:
            return

        set_clauses.append("UPDATED_AT = CURRENT_TIMESTAMP")
        with self._get_cursor(commit=True) as cur:
            cur.execute(
                f"UPDATE {self.collection_name} SET {', '.join(set_clauses)} WHERE ID = :vector_id",
                params,
            )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector payload by ID."""
        with self._get_cursor() as cur:
            cur.execute(f"SELECT ID, PAYLOAD FROM {self.collection_name} WHERE ID = :vector_id", {"vector_id": vector_id})
            result = cur.fetchone()

        if not result:
            return None
        return OutputData(id=str(result[0]), score=None, payload=self._payload_from_db(result[1]))

    def list_cols(self) -> List[str]:
        """List Oracle tables visible to the current user."""
        with self._get_cursor() as cur:
            cur.execute("SELECT table_name FROM user_tables")
            return [row[0] for row in cur.fetchall()]

    def delete_col(self) -> None:
        """Drop the Oracle table used as a Mem0 collection."""
        with self._get_cursor(commit=True) as cur:
            if self._table_exists(cur):
                cur.execute(f"DROP TABLE {self.collection_name} PURGE")

    def col_info(self) -> dict[str, Any]:
        """Get row count and segment size for the Oracle collection."""
        with self._get_cursor() as cur:
            cur.execute(f"SELECT COUNT(*) FROM {self.collection_name}")
            count = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COALESCE(SUM(bytes), 0)
                FROM user_segments
                WHERE segment_name = :segment_name
                """,
                {"segment_name": self.collection_name},
            )
            size = cur.fetchone()[0]
        return {"name": self.collection_name, "count": count, "size": size}

    def list(self, filters: Optional[dict] = None, top_k: Optional[int] = 100) -> List[OutputData]:
        """List vectors in the Oracle collection."""
        filter_clause, params = self._build_filter_clause(filters)
        top_k = int(top_k or 100)
        if top_k < 1:
            raise ValueError("top_k must be greater than zero.")

        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT ID, PAYLOAD
                FROM {self.collection_name}
                {filter_clause}
                FETCH FIRST {top_k} ROWS ONLY
                """,
                params,
            )
            results = cur.fetchall()

        return [OutputData(id=str(row[0]), score=None, payload=self._payload_from_db(row[1])) for row in results]

    def reset(self) -> None:
        """Reset the Oracle collection by dropping and recreating the table and indexes."""
        logger.warning(f"Resetting Oracle collection {self.collection_name}...")
        self.delete_col()
        self.create_col()

    def __del__(self) -> None:
        """Close an owned Oracle connection pool when this provider is destroyed."""
        try:
            if self._owns_pool and self.connection_pool:
                self.connection_pool.close()
        except Exception:
            pass
