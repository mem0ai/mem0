import json
import logging
import uuid
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    import pymysql
    from pymysql.cursors import DictCursor
    from dbutils.pooled_db import PooledDB
except ImportError:
    raise ImportError(
        "PolarDB vector store requires PyMySQL and DBUtils. "
        "Please install them using 'pip install pymysql dbutils'"
    )

from mem0.configs.vector_stores.polardb import SUPPORTED_INDEX_TYPES
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Mapping from mem0 metric names to PolarDB DISTANCE function metric names
METRIC_MAP = {
    "cosine": "COSINE",
    "euclidean": "EUCLIDEAN",
    "inner_product": "DOT",
}


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class PolarDB(VectorStoreBase):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        database: str,
        collection_name: str,
        embedding_model_dims: int,
        metric: str = "cosine",
        index_type: str = "FAISS_HNSW_FLAT",
        hnsw_m: int = 16,
        hnsw_ef_construction: int = 200,
        pq_m: Optional[int] = None,
        pq_nbits: Optional[int] = None,
        sq_type: Optional[str] = None,
        ssl_ca: Optional[str] = None,
        ssl_disabled: bool = False,
        minconn: int = 1,
        maxconn: int = 5,
        connection_pool: Optional[Any] = None,
    ):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.metric = metric
        self.index_type = index_type
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self.pq_m = pq_m
        self.pq_nbits = pq_nbits
        self.sq_type = sq_type
        self.ssl_ca = ssl_ca
        self.ssl_disabled = ssl_disabled
        self.connection_pool = connection_pool

        if self.metric not in METRIC_MAP:
            raise ValueError(f"Unsupported metric '{self.metric}'. Must be one of: {list(METRIC_MAP.keys())}")
        if self.index_type not in SUPPORTED_INDEX_TYPES:
            raise ValueError(
                f"Unsupported index_type '{self.index_type}'. Must be one of: {list(SUPPORTED_INDEX_TYPES)}"
            )

        self.polardb_metric = METRIC_MAP[self.metric]

        if self.connection_pool is None:
            self._setup_connection_pool(minconn, maxconn)

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(name=collection_name, vector_size=embedding_model_dims, distance=metric)

    def _setup_connection_pool(self, minconn: int, maxconn: int):
        """Setup MySQL connection pool with PolarDB vector search session variables."""
        connect_kwargs = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": False,
            "init_command": (
                "SET imci_enable_vector_search = ON; "
                "SET cost_threshold_for_imci = 0"
            ),
        }

        if not self.ssl_disabled:
            ssl_config = {"ssl_verify_cert": True}
            if self.ssl_ca:
                ssl_config["ssl_ca"] = self.ssl_ca
            connect_kwargs["ssl"] = ssl_config

        try:
            self.connection_pool = PooledDB(
                creator=pymysql,
                mincached=minconn,
                maxcached=maxconn,
                maxconnections=maxconn,
                blocking=True,
                **connect_kwargs,
            )
            logger.info("Successfully created PolarDB connection pool")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    @contextmanager
    def _get_cursor(self):
        """Context manager to get a cursor from the connection pool.

        Always ends the transaction (commit or rollback) before returning the
        connection to the pool.  This is critical for PolarDB with IMCI: when
        ``cost_threshold_for_imci = 0`` all queries are routed to the columnar
        engine, which honours the transaction-level read-view.  If we leave a
        connection in an open transaction, a subsequent read on the same pooled
        connection would see a *stale* snapshot and miss recently committed rows.
        """
        conn = self.connection_pool.connection()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"Database error: {exc}", exc_info=True)
            raise
        finally:
            cur.close()
            conn.close()

    @staticmethod
    def _vector_to_bytes(v: list) -> bytes:
        """Convert a vector (list of floats) to binary bytes for PolarDB VECTOR type."""
        return np.array(v, dtype="float32").tobytes()

    @staticmethod
    def _bytes_to_vector(b: bytes) -> list:
        """Convert binary bytes from PolarDB VECTOR type back to a list of floats."""
        return np.frombuffer(b, dtype="float32").tolist()

    @staticmethod
    def _filter_value(v):
        """Convert a non-string filter value to a string suitable for JSON_UNQUOTE comparison."""
        if isinstance(v, bool):
            return "true" if v else "false"
        return str(v)

    @staticmethod
    def _build_filter_clause(filters: Optional[Dict]) -> tuple:
        """Build WHERE clause from filters using JSON_UNQUOTE for IMCI compatibility.

        PolarDB IMCI does not reliably support implicit JSON-to-VARCHAR comparison,
        so we extract the value as a plain string with JSON_UNQUOTE and compare
        against the raw value.
        """
        if not filters:
            return "", []
        conditions = []
        params = []
        for k, v in filters.items():
            conditions.append("JSON_UNQUOTE(JSON_EXTRACT(payload, %s)) = %s")
            params.extend([f"$.{k}", v if isinstance(v, str) else PolarDB._filter_value(v)])
        return "WHERE " + " AND ".join(conditions), params

    def _build_vector_index_comment(self) -> str:
        """Build the IMCI vector index comment string for column definition."""
        params = (
            f"metric={self.polardb_metric.lower()},"
            f"max_degree={self.hnsw_m},"
            f"ef_construction={self.hnsw_ef_construction}"
        )

        if self.index_type == "FAISS_HNSW_PQ":
            params += f",pq_m={self.pq_m},pq_nbits={self.pq_nbits}"
        elif self.index_type == "FAISS_HNSW_SQ":
            params += f",sq_type={self.sq_type}"

        return f"imci_vector_index={self.index_type}({params})"

    def create_col(self, name: str = None, vector_size: int = None, distance=None):
        """Create a new collection (table) with PolarDB native VECTOR type and HNSW index."""
        table_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims
        vector_index_comment = self._build_vector_index_comment()

        with self._get_cursor() as cur:
            cur.execute(
                f"CREATE TABLE IF NOT EXISTS `{table_name}` ("
                f"id VARCHAR(255) PRIMARY KEY, "
                f'vector VECTOR({dims}) COMMENT "{vector_index_comment}", '
                f"payload JSON"
                f") ENGINE=InnoDB COMMENT 'COLUMNAR=1'"
            )
            logger.info(f"Created collection '{table_name}' with VECTOR({dims}) and HNSW index")

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """Insert vectors into the collection using binary encoding."""
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        data = [
            (vec_id, self._vector_to_bytes(vector), json.dumps(payload))
            for vec_id, vector, payload in zip(ids, vectors, payloads)
        ]

        with self._get_cursor() as cur:
            cur.executemany(
                f"INSERT INTO `{self.collection_name}` (id, vector, payload) "
                f"VALUES (%s, _binary %s, %s) "
                f"ON DUPLICATE KEY UPDATE vector = VALUES(vector), payload = VALUES(payload)",
                data,
            )

    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """Search for similar vectors using PolarDB native DISTANCE function with HNSW index."""
        filter_clause, filter_params = self._build_filter_clause(filters)
        query_vector_bytes = self._vector_to_bytes(vectors)

        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, DISTANCE(vector, _binary %s, '{self.polardb_metric}') AS score, payload "
                f"FROM `{self.collection_name}` "
                f"{filter_clause} "
                f"ORDER BY score ASC LIMIT %s",
                (query_vector_bytes, *filter_params, limit),
            )
            results = cur.fetchall()

        return [
            OutputData(
                id=r["id"],
                score=float(r["score"]),
                payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            )
            for r in results
        ]

    def delete(self, vector_id: str):
        """Delete a vector by ID."""
        with self._get_cursor() as cur:
            cur.execute(f"DELETE FROM `{self.collection_name}` WHERE id = %s", (vector_id,))

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """Update a vector and/or its payload."""
        set_clauses = []
        params = []

        if vector is not None:
            set_clauses.append("vector = _binary %s")
            params.append(self._vector_to_bytes(vector))
        if payload is not None:
            set_clauses.append("payload = %s")
            params.append(json.dumps(payload))

        if not set_clauses:
            return

        params.append(vector_id)
        with self._get_cursor() as cur:
            cur.execute(
                f"UPDATE `{self.collection_name}` SET {', '.join(set_clauses)} WHERE id = %s",
                tuple(params),
            )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a vector by ID."""
        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, payload FROM `{self.collection_name}` WHERE id = %s",
                (vector_id,),
            )
            result = cur.fetchone()
            if not result:
                return None
            return OutputData(
                id=result["id"],
                score=None,
                payload=json.loads(result["payload"]) if isinstance(result["payload"], str) else result["payload"],
            )

    def list_cols(self) -> List[str]:
        """List all collections (tables)."""
        with self._get_cursor() as cur:
            cur.execute("SHOW TABLES")
            return [row[f"Tables_in_{self.database}"] for row in cur.fetchall()]

    def delete_col(self):
        """Delete the collection (table)."""
        with self._get_cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS `{self.collection_name}`")
        logger.info(f"Deleted collection '{self.collection_name}'")

    def col_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        with self._get_cursor() as cur:
            cur.execute(
                """
                SELECT
                    TABLE_NAME as name,
                    TABLE_ROWS as count,
                    ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as size_mb
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
                """,
                (self.database, self.collection_name),
            )
            result = cur.fetchone()

        if result:
            return {
                "name": result["name"],
                "count": result["count"],
                "size": f"{result['size_mb']} MB",
            }
        return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100,
    ) -> List[List[OutputData]]:
        """List all vectors in the collection with optional filtering."""
        filter_clause, filter_params = self._build_filter_clause(filters)

        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, payload FROM `{self.collection_name}` {filter_clause} LIMIT %s",
                (*filter_params, limit),
            )
            results = cur.fetchall()

        return [
            [
                OutputData(
                    id=r["id"],
                    score=None,
                    payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
                )
                for r in results
            ]
        ]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(name=self.collection_name, vector_size=self.embedding_model_dims)

    def __del__(self):
        """Close the connection pool when the object is deleted."""
        try:
            if hasattr(self, "connection_pool") and self.connection_pool:
                self.connection_pool.close()
        except Exception:
            pass
