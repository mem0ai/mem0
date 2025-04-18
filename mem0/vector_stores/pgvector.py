import json
import logging
from typing import List, Optional, Dict, Any
from contextlib import contextmanager

from pydantic import BaseModel

try:
    import psycopg2
    from psycopg2.extras import execute_values
    from psycopg2.pool import SimpleConnectionPool
except ImportError:
    raise ImportError("The 'psycopg2' library is required. Please install it using 'pip install psycopg2'.")

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class PGVector(VectorStoreBase):
    def __init__(
        self,
        dbname: str,
        collection_name: str,
        embedding_model_dims: int,
        user: str,
        password: str,
        host: str,
        port: int,
        diskann: bool,
        hnsw: bool,
        use_pool: bool = False,
        min_pool_size: int = 1,
        max_pool_size: int = 20,
    ):
        """
        Initialize the PGVector database.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str): Database host
            port (int): Database port
            diskann (bool): Use DiskANN for faster search
            hnsw (bool): Use HNSW for faster search
            use_pool (bool): Use connection pooling
            min_pool_size (int): Minimum number of connections in pool
            max_pool_size (int): Maximum number of connections in pool
        """
        self.collection_name = collection_name
        self.use_diskann = diskann
        self.use_hnsw = hnsw
        self.use_pool = use_pool

        # Store connection params for reconnection if needed
        self.connection_params = {
            "dbname": dbname,
            "user": user,
            "password": password,
            "host": host,
            "port": port,
        }

        if self.use_pool:
            logger.info(f"Using connection pooling, min_pool_size={min_pool_size}, max_pool_size={max_pool_size}")
            self.pool = SimpleConnectionPool(
                min_pool_size,
                max_pool_size,
                **self.connection_params
            )
            # Get initial connection for setup
            self.conn = self.pool.getconn()
        else:
            self.pool = None
            self.conn = psycopg2.connect(**self.connection_params)

        self.cur = self.conn.cursor()

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(embedding_model_dims)

        # Return initial connection to pool if using pooling
        if self.use_pool:
            self.pool.putconn(self.conn)
            self.conn = None
            self.cur = None

    @contextmanager
    def get_connection(self):
        """Context manager for handling connections from pool or direct connection."""
        if self.use_pool:
            conn = self.pool.getconn()
            try:
                yield conn
            finally:
                self.pool.putconn(conn)
        else:
            yield self.conn

    @contextmanager
    def get_cursor(self):
        """Context manager for handling cursors."""
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                yield cur

    def create_col(self, embedding_model_dims):
        """
        Create a new collection (table in PostgreSQL).
        Will also initialize vector search index if specified.

        Args:
            embedding_model_dims (int): Dimension of the embedding vector.
        """
        with self.get_cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    id UUID PRIMARY KEY,
                    vector vector({embedding_model_dims}),
                    payload JSONB
                );
                """
            )

            if self.use_diskann and embedding_model_dims < 2000:
                cur.execute("SELECT * FROM pg_extension WHERE extname = 'vectorscale'")
                if cur.fetchone():
                    cur.execute(
                        f"""
                        CREATE INDEX IF NOT EXISTS {self.collection_name}_diskann_idx
                        ON {self.collection_name}
                        USING diskann (vector);
                        """
                    )
            elif self.use_hnsw:
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_hnsw_idx
                    ON {self.collection_name}
                    USING hnsw (vector vector_cosine_ops)
                    """
                )

            conn = cur.connection
            conn.commit()

    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        """
        Insert vectors into a collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert.
            payloads (List[Dict], optional): List of payloads corresponding to vectors.
            ids (List[str], optional): List of IDs corresponding to vectors.
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        json_payloads = [json.dumps(payload) for payload in payloads]
        data = [(id, vector, payload) for id, vector, payload in zip(ids, vectors, json_payloads)]

        with self.get_cursor() as cur:
            execute_values(
                cur,
                f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES %s",
                data,
            )
            cur.connection.commit()

    def search(self, query: str, vectors: List[float], limit: int = 5, filters: Optional[Dict] = None):
        """
        Search for similar vectors.

        Args:
            query (str): Query.
            vectors (List[float]): Query vector.
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            list: Search results.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self.get_cursor() as cur:
            cur.execute(
                f"""
                SELECT id, vector <=> %s::vector AS distance, payload
                FROM {self.collection_name}
                {filter_clause}
                ORDER BY distance
                LIMIT %s
                """,
                (vectors, *filter_params, limit),
            )
            results = cur.fetchall()
            return [OutputData(id=str(r[0]), score=float(r[1]), payload=r[2]) for r in results]

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        with self.get_cursor() as cur:
            cur.execute(f"DELETE FROM {self.collection_name} WHERE id = %s", (vector_id,))
            cur.connection.commit()

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[Dict] = None):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        with self.get_cursor() as cur:
            if vector:
                cur.execute(
                    f"UPDATE {self.collection_name} SET vector = %s WHERE id = %s",
                    (vector, vector_id),
                )
            if payload:
                cur.execute(
                    f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                    (psycopg2.extras.Json(payload), vector_id),
                )
            cur.connection.commit()

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        with self.get_cursor() as cur:
            cur.execute(
                f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = %s",
                (vector_id,),
            )
            result = cur.fetchone()
            if not result:
                return None
            return OutputData(id=str(result[0]), score=None, payload=result[2])

    def list_cols(self) -> List[str]:
        """
        List all collections.

        Returns:
            List[str]: List of collection names.
        """
        with self.get_cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return [row[0] for row in cur.fetchall()]

    def delete_col(self):
        """Delete a collection."""
        with self.get_cursor() as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.collection_name}")
            cur.connection.commit()

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        with self.get_cursor() as cur:
            cur.execute(
                f"""
                SELECT 
                    table_name, 
                    (SELECT COUNT(*) FROM {self.collection_name}) as row_count,
                    (SELECT pg_size_pretty(pg_total_relation_size('{self.collection_name}'))) as total_size
                FROM information_schema.tables 
                WHERE table_schema = 'public' AND table_name = %s
                """,
                (self.collection_name,),
            )
            result = cur.fetchone()
            return {"name": result[0], "count": result[1], "size": result[2]}

    def list(self, filters=None, limit=100):
        """
        List all vectors in a collection.

        Args:
            filters (Dict, optional): Filters to apply to the list.
            limit (int, optional): Number of vectors to return. Defaults to 100.

        Returns:
            List[OutputData]: List of vectors.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        query = f"""
            SELECT id, vector, payload
            FROM {self.collection_name}
            {filter_clause}
            LIMIT %s
        """

        self.cur.execute(query, (*filter_params, limit))

        results = self.cur.fetchall()
        return [[OutputData(id=str(r[0]), score=None, payload=r[2]) for r in results]]

    def close(self):
        """Explicitly close all connections."""
        if self.use_pool:
            if self.pool is not None:
                self.pool.closeall()
                self.pool = None
        else:
            if hasattr(self, "cur") and self.cur is not None:
                self.cur.close()
                self.cur = None
            if hasattr(self, "conn") and self.conn is not None:
                self.conn.close()
                self.conn = None

    def __del__(self):
        """Ensure connections are closed on deletion."""
        self.close()

    def __enter__(self):
        """Support for context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensure connections are closed when exiting context."""
        self.close()
