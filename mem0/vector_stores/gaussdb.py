import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    import gaussdb  # noqa: F401
    from gaussdb_pool import ConnectionPool
    from gaussdb.rows import dict_row
    from gaussdb.types.json import Jsonb
    GAUSSDB_AVAILABLE = True
except ImportError:
    GAUSSDB_AVAILABLE = False
    ConnectionPool = None
    dict_row = None
    Jsonb = None

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class GaussDB(VectorStoreBase):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: Optional[str],
        dbname: str,
        collection_name: str,
        embedding_model_dims: int,
        diskann: bool = False,
        hnsw: bool = False,
        sslmode: Optional[str] = None,
        minconn: int = 1,
        maxconn: int = 5,
        connection_string: Optional[str] = None,
        connection_pool: Optional[Any] = None,
    ):
        """
        Initialize the GaussDB vector store.

        Args:
            host (str): GaussDB server host.
            port (int): GaussDB server port.
            user (str): Database user.
            password (str, optional): Database password.
            dbname (str): Database name.
            collection_name (str): Table name used as collection.
            embedding_model_dims (int): Dimension of the embedding vector.
            diskann (bool): Use DiskANN index for faster search.
            hnsw (bool): Use HNSW index for faster search.
            sslmode (str, optional): SSL mode (e.g., 'disable', 'require', 'verify-full').
            minconn (int): Minimum number of connections in the pool.
            maxconn (int): Maximum number of connections in the pool.
            connection_string (str, optional): Full DSN connection string (overrides individual parameters).
            connection_pool (Any, optional): Pre-configured connection pool object.
        """
        if not GAUSSDB_AVAILABLE:
            raise ImportError(
                "GaussDB vector store requires the gaussdb package. "
                "Install with: pip install gaussdb gaussdb-pool"
            )

        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.use_diskann = diskann
        self.hnsw = hnsw

        if connection_pool is not None:
            self.connection_pool = connection_pool
        else:
            conninfo = connection_string or (
                f"host={host} port={port} user={user} "
                f"password={password} dbname={dbname}"
            )
            if sslmode:
                conninfo = f"{conninfo} sslmode={sslmode}"
            self.connection_pool = ConnectionPool(
                conninfo, min_size=minconn, max_size=maxconn, open=True
            )
            logger.info("GaussDB connection pool created")

        if collection_name not in self.list_cols():
            self.create_col(collection_name, embedding_model_dims)

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        """
        Unified context manager to get a cursor from the connection pool.
        Auto-commits or rolls back based on exception, and returns the connection to the pool.
        """
        with self.connection_pool.connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                try:
                    yield cur
                    if commit:
                        conn.commit()
                except Exception as exc:
                    conn.rollback()
                    logger.error(f"Database error: {exc}", exc_info=True)
                    raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table in GaussDB).
        Will also initialize vector search index (DiskANN or HNSW) if specified.
        """
        table = name or self.collection_name
        dims = vector_size or self.embedding_model_dims
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id      UUID PRIMARY KEY,
                    vector  vector({dims}),
                    payload JSONB
                )
            """)
            if self.use_diskann:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS {table}_diskann_idx
                    ON {table} USING diskann (vector vector_cosine_ops)
                """)
            elif self.hnsw:
                cur.execute(f"""
                    CREATE INDEX IF NOT EXISTS {table}_hnsw_idx
                    ON {table} USING hnsw (vector vector_cosine_ops)
                """)
        logger.info(f"Created collection '{table}' (dims={dims}, diskann={self.use_diskann}, hnsw={self.hnsw})")

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors into the collection. Uses executemany for batch insertion
        with ON DUPLICATE KEY UPDATE for upsert semantics.

        Args:
            vectors (List[List[float]]): List of embedding vectors.
            payloads (List[Dict], optional): List of metadata payloads.
            ids (List[str], optional): List of vector IDs. Auto-generated UUIDs if not provided.
        """
        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        data = [(vid, str(vec), Jsonb(pl)) for vid, vec, pl in zip(ids, vectors, payloads)]
        with self._get_cursor(commit=True) as cur:
            cur.executemany(
                f"INSERT INTO {self.collection_name} (id, vector, payload) "
                f"VALUES (%s, %s, %s) "
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
        """
        Search for similar vectors using cosine distance.

        Args:
            query (str): Query string (unused, kept for interface compatibility).
            vectors (List[float]): Query vector.
            limit (int): Number of results to return. Defaults to 5.
            filters (Dict, optional): JSONB payload filters to apply.

        Returns:
            List[OutputData]: Search results sorted by distance.
        """
        conditions, params = [], []
        if filters:
            for k, v in filters.items():
                conditions.append("payload->>%s = %s")
                params.extend([k, str(v)])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT id, vector <=> %s::vector AS distance, payload
                FROM {self.collection_name}
                {where}
                ORDER BY distance
                LIMIT %s
                """,
                [str(vectors)] + params + [limit],
            )
            results = cur.fetchall()

        return [
            OutputData(
                id=str(r["id"]),
                score=float(r["distance"]),
                payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            )
            for r in results
        ]

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DELETE FROM {self.collection_name} WHERE id = %s", (vector_id,))

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and/or its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        with self._get_cursor(commit=True) as cur:
            if vector is not None:
                cur.execute(
                    f"UPDATE {self.collection_name} SET vector = %s::vector WHERE id = %s",
                    (str(vector), vector_id),
                )
            if payload is not None:
                cur.execute(
                    f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                    (Jsonb(payload), vector_id),
                )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector, or None if not found.
        """
        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, payload FROM {self.collection_name} WHERE id = %s",
                (vector_id,),
            )
            r = cur.fetchone()
        if not r:
            return None
        return OutputData(
            id=str(r["id"]),
            score=None,
            payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
        )

    def list_cols(self) -> List[str]:
        """
        List all collections (tables) in the public schema.

        Returns:
            List[str]: List of collection names.
        """
        with self._get_cursor() as cur:
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"
            )
            return [row["table_name"] for row in cur.fetchall()]

    def delete_col(self):
        """Delete the current collection."""
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.collection_name}")
        logger.info(f"Deleted collection '{self.collection_name}'")

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the current collection.

        Returns:
            Dict[str, Any]: Collection info with name, count, and size. Empty dict if not found.
        """
        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT table_name,
                       (SELECT COUNT(*) FROM {self.collection_name}) AS row_count,
                       pg_size_pretty(pg_total_relation_size('{self.collection_name}')) AS total_size
                FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (self.collection_name,),
            )
            r = cur.fetchone()
        return (
            {"name": r["table_name"], "count": r["row_count"], "size": r["total_size"]}
            if r
            else {}
        )

    def list(self, filters: Optional[Dict] = None, limit: int = 100) -> List[List[OutputData]]:
        """
        List all vectors in the collection.

        Args:
            filters (Dict, optional): JSONB payload filters to apply.
            limit (int): Maximum number of vectors to return. Defaults to 100.

        Returns:
            List[List[OutputData]]: List of vectors.
        """
        conditions, params = [], []
        if filters:
            for k, v in filters.items():
                conditions.append("payload->>%s = %s")
                params.extend([k, str(v)])
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, payload FROM {self.collection_name} {where} LIMIT %s",
                (*params, limit),
            )
            results = cur.fetchall()
        return [[
            OutputData(
                id=str(r["id"]),
                score=None,
                payload=json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"],
            )
            for r in results
        ]]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(name=self.collection_name, vector_size=self.embedding_model_dims)

    def __del__(self):
        """Close the database connection pool when the object is deleted."""
        try:
            if hasattr(self, "connection_pool") and self.connection_pool:
                self.connection_pool.close()
        except Exception:
            pass
