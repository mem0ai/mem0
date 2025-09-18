import json
import logging
from contextlib import contextmanager
from typing import Any, List, Optional

from pydantic import BaseModel

# Try to import psycopg (psycopg3) first, then fall back to psycopg2
try:
    from psycopg.types.json import Json
    from psycopg_pool import ConnectionPool
    PSYCOPG_VERSION = 3
    logger = logging.getLogger(__name__)
    logger.info("Using psycopg (psycopg3) with ConnectionPool for PostgreSQL connections")
except ImportError:
    try:
        from psycopg2.extras import Json, execute_values
        from psycopg2.pool import ThreadedConnectionPool as ConnectionPool
        PSYCOPG_VERSION = 2
        logger = logging.getLogger(__name__)
        logger.info("Using psycopg2 with ThreadedConnectionPool for PostgreSQL connections")
    except ImportError:
        raise ImportError(
            "Neither 'psycopg' nor 'psycopg2' library is available. "
            "Please install one of them using 'pip install psycopg[pool]' or 'pip install psycopg2'"
        )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class Aurora(VectorStoreBase):
    def __init__(
        self,
        dbname,
        collection_name,
        embedding_model_dims,
        user,
        password,
        host,
        port,
        index_type="hnsw",
        distance="cosine",
        minconn=1,
        maxconn=5,
        hnsw_m=16,
        hnsw_ef_construction=200,
        hnsw_iterative_scan="relaxed_order",
        ivfflat_iterative_scan="relaxed_order",
        ivfflat_list=100,
        max_parallel_maintenance_workers=4,
        sslmode=None,
        connection_string=None,
        connection_pool=None,
    ):
        """
        Initialize the Aurora PostgreSQL Pgvector database.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str, optional): Database host
            port (int, optional): Database port
            index_type (str, optional): Index type ('hnsw' or 'ivfflat'). Defaults to "hnsw".
            distance (str, optional):  Distance metric to use. Defaults to None, which uses 'cosine'.
            minconn (int): Minimum number of connections to keep in the connection pool
            maxconn (int): Maximum number of connections allowed in the connection pool
            hnsw_m (int, optional): HNSW M parameter (connections per node). Defaults to 16.
            hnsw_ef_construction (int, optional): HNSW ef_construction parameter. Defaults to 200.
            hnsw_iterative_scan (str, optional): automatically scan more of the index when needed for hnsw. Defaults to enabled.
            ivfflat_iterative_scan (str, optional): automatically scan more of the index when needed for ivfflat. Defaults to enabled.
            ivfflat_list: An IVFFlat index divides vectors into lists and then searches a subset of those lists that are closest to the query vector.Default to be 100.
            max_parallel_maintenance_workers: Sets the maximum number of parallel workers that can be started by a single utility command. Defaults to 4.
            sslmode (str, optional): SSL mode for PostgreSQL connection (e.g., 'require', 'prefer', 'disable')
            connection_string (str, optional): PostgreSQL connection string (overrides individual connection parameters)
            connection_pool (Any, optional): psycopg2 connection pool object (overrides connection string and individual parameters)
        """
        self.collection_name = collection_name
        self.index_type = index_type.lower().strip()
        self.distance = distance.lower().strip()
        self.hnsw_iterative_scan = hnsw_iterative_scan.lower().strip()
        self.hnsw_m = hnsw_m
        self.hnsw_ef_construction = hnsw_ef_construction
        self.ivfflat_iterative_scan = ivfflat_iterative_scan.lower().strip()
        self.ivfflat_list = ivfflat_list
        self.max_parallel_maintenance_workers = max_parallel_maintenance_workers
        self.embedding_model_dims = embedding_model_dims
        self.connection_pool = None
        self.vector_ops = {"cosine":"<=>", "l1":"<+>", "l2":"<->", "ip":"<#>", "hamming":"<~>", "jaccard":"<%>"}
        self.subvectors = {"cosine":"(vector vector_cosine_ops)", "l1":"(vector vector_l1_ops)", "l2":"(vector vector_l2_ops)", "ip":"(vector vector_ip_ops)", "hamming":"(vector bit_hamming_ops)", "jaccard":"(vector bit_jaccard_ops)"}

        # Validate index type
        if self.index_type not in ["hnsw", "ivfflat"]:
            raise ValueError(f"Invalid index_type: {index_type}. Must be 'hnsw' or 'ivfflat'")
        
        # Validate distance
        if self.distance not in ["cosine", "l1", "l2", "ip", "hamming", "jaccard"]:
            raise ValueError(f"Invalid distance: {distance}. Must be 'cosine' or 'L1' or 'L2' or 'IP' or 'Hamming' or 'Jaccard'")
        
        #validate iterative scan
        if self.hnsw_iterative_scan not in ["strict_order","relaxed_order","off"]:
            raise ValueError(f"Invalid hnsw_iterative_scan: {self.hnsw_iterative_scan}. Must be 'strict_order' or 'relaxed_order' or 'off'")
        if self.ivfflat_iterative_scan not in ["relaxed_order","off"]:
            raise ValueError(f"Invalid ivfflat_iterative_scan: {self.ivfflat_iterative_scan}. Must be 'relaxed_order' or 'off'")

        # Connection setup with priority: connection_pool > connection_string > individual parameters
        if connection_pool is not None:
            # Use provided connection pool
            self.connection_pool = connection_pool
        elif connection_string:
            if sslmode:
                # Append sslmode to connection string if provided
                if 'sslmode=' in connection_string:
                    # Replace existing sslmode
                    import re
                    connection_string = re.sub(r'sslmode=[^ ]*', f'sslmode={sslmode}', connection_string)
                else:
                    # Add sslmode to connection string
                    connection_string = f"{connection_string} sslmode={sslmode}"
        else:
            connection_string = f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
            if sslmode:
                connection_string = f"{connection_string} sslmode={sslmode}"
        
        if self.connection_pool is None:
            if PSYCOPG_VERSION == 3:
                # psycopg3 ConnectionPool
                self.connection_pool = ConnectionPool(conninfo=connection_string, min_size=minconn, max_size=maxconn, open=True)
            else:
                # psycopg2 ThreadedConnectionPool
                self.connection_pool = ConnectionPool(minconn=minconn, maxconn=maxconn, dsn=connection_string)

        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col()

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        """
        Unified context manager to get a cursor from the appropriate pool.
        Auto-commits or rolls back based on exception, and returns the connection to the pool.
        """
        if PSYCOPG_VERSION == 3:
            # psycopg3 auto-manages commit/rollback and pool return
            with self.connection_pool.connection() as conn:
                with conn.cursor() as cur:
                    try:
                        yield cur
                        if commit:
                            conn.commit()
                    except Exception:
                        conn.rollback()
                        logger.error("Error in cursor context (psycopg3)", exc_info=True)
                        raise
        else:
            # psycopg2 manual getconn/putconn
            conn = self.connection_pool.getconn()
            cur = conn.cursor()
            try:
                yield cur
                if commit:
                    conn.commit()
            except Exception as exc:
                conn.rollback()
                logger.error(f"Error occurred: {exc}")
                raise exc
            finally:
                cur.close()
                self.connection_pool.putconn(conn)

    def create_col(self) -> None:
        """
        Create a new collection (table in Aurora PostgreSQL).
        Will also initialize vector search index if specified.
        """
        distance_metric = self.subvectors[self.distance]
        with self._get_cursor(commit=True) as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {self.collection_name} (
                    id UUID PRIMARY KEY,
                    vector vector({self.embedding_model_dims}),
                    payload JSONB
                );
                """
            )
            if self.index_type == "hnsw":
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_hnsw_idx
                    ON {self.collection_name}
                    USING hnsw {distance_metric}
                    with (m = {self.hnsw_m}, ef_construction = {self.hnsw_ef_construction})
                    """
                )
                cur.execute(
                    f"""
                    SET hnsw.iterative_scan = {self.hnsw_iterative_scan}
                    """
                )

            elif self.index_type == "ivfflat":
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {self.collection_name}_ivfflat_idx
                    ON {self.collection_name}
                    USING ivfflat {distance_metric}
                    with (lists = {self.ivfflat_list})
                    """
                )
                cur.execute(
                    f"""
                    SET ivfflat.iterative_scan = {self.ivfflat_iterative_scan}
                    """
                )
            cur.execute(
                f"""
                SET max_parallel_maintenance_workers = {self.max_parallel_maintenance_workers}
                """
            )

    def insert(self, vectors: list[list[float]], payloads=None, ids=None) -> None:
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        json_payloads = [json.dumps(payload) for payload in payloads]

        data = [(id, vector, payload) for id, vector, payload in zip(ids, vectors, json_payloads)]
        if PSYCOPG_VERSION == 3:
            with self._get_cursor(commit=True) as cur:
                cur.executemany(
                    f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES (%s, %s, %s)",
                    data,
                )
        else:
            with self._get_cursor(commit=True) as cur:
                execute_values(
                    cur,
                    f"INSERT INTO {self.collection_name} (id, vector, payload) VALUES %s",
                    data,
                )

    def search(
        self,
        query: str,
        vectors: list[float],
        limit: Optional[int] = 5,
        filters: Optional[dict] = None,
    ) -> List[OutputData]:
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
        operator = self.vector_ops[self.distance]
        if filters:
            for k, v in filters.items():
                filter_conditions.append("payload->>%s = %s")
                filter_params.extend([k, str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT id, vector {operator} %s::vector AS distance, payload
                FROM {self.collection_name}
                {filter_clause}
                ORDER BY distance
                LIMIT %s
                """,
                (vectors, *filter_params, limit),
            )

            results = cur.fetchall()
        return [OutputData(id=str(r[0]), score=float(r[1]), payload=r[2]) for r in results]

    def delete(self, vector_id: str) -> None:
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
        vector: Optional[list[float]] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        with self._get_cursor(commit=True) as cur:
            if vector:
               cur.execute(
                    f"UPDATE {self.collection_name} SET vector = %s WHERE id = %s",
                    (vector, vector_id),
                )
            if payload:
                # Handle JSON serialization based on psycopg version
                if PSYCOPG_VERSION == 3:
                    # psycopg3 uses psycopg.types.json.Json
                    cur.execute(
                        f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                        (Json(payload), vector_id),
                    )
                else:
                    # psycopg2 uses psycopg2.extras.Json
                    cur.execute(
                        f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                        (Json(payload), vector_id),
                    )


    def get(self, vector_id: str) -> OutputData:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector.
        """
        with self._get_cursor() as cur:
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
        with self._get_cursor() as cur:
            cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            return [row[0] for row in cur.fetchall()]

    def delete_col(self) -> None:
        """Delete a collection."""
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DROP TABLE IF EXISTS {self.collection_name}")

    def col_info(self) -> dict[str, Any]:
        """
        Get information about a collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        with self._get_cursor() as cur:
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

    def list(
        self,
        filters: Optional[dict] = None,
        limit: Optional[int] = 100
    ) -> List[OutputData]:
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

        with self._get_cursor() as cur:
            cur.execute(query, (*filter_params, limit))
            results = cur.fetchall()
        return [[OutputData(id=str(r[0]), score=None, payload=r[2]) for r in results]]

    def __del__(self) -> None:
        """
        Close the database connection pool when the object is deleted.
        """
        try:
            # Close pool appropriately
            if PSYCOPG_VERSION == 3:
                self.connection_pool.close()
            else:
                self.connection_pool.closeall()
        except Exception:
            pass

    def reset(self) -> None:
        """Reset the index by deleting and recreating it."""
        logger.warning(f"Resetting index {self.collection_name}...")
        self.delete_col()
        self.create_col()
