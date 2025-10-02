import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    import pymysql
    from pymysql.cursors import DictCursor
    from dbutils.pooled_db import PooledDB
except ImportError:
    raise ImportError(
        "Azure MySQL vector store requires PyMySQL and DBUtils. "
        "Please install them using 'pip install pymysql dbutils'"
    )

try:
    from azure.identity import DefaultAzureCredential
    AZURE_IDENTITY_AVAILABLE = True
except ImportError:
    AZURE_IDENTITY_AVAILABLE = False

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class AzureMySQL(VectorStoreBase):
    def __init__(
        self,
        host: str,
        port: int,
        user: str,
        password: Optional[str],
        database: str,
        collection_name: str,
        embedding_model_dims: int,
        use_azure_credential: bool = False,
        ssl_ca: Optional[str] = None,
        ssl_disabled: bool = False,
        minconn: int = 1,
        maxconn: int = 5,
        connection_pool: Optional[Any] = None,
    ):
        """
        Initialize the Azure MySQL vector store.

        Args:
            host (str): MySQL server host
            port (int): MySQL server port
            user (str): Database user
            password (str, optional): Database password (not required if using Azure credential)
            database (str): Database name
            collection_name (str): Collection/table name
            embedding_model_dims (int): Dimension of the embedding vector
            use_azure_credential (bool): Use Azure DefaultAzureCredential for authentication
            ssl_ca (str, optional): Path to SSL CA certificate
            ssl_disabled (bool): Disable SSL connection
            minconn (int): Minimum number of connections in the pool
            maxconn (int): Maximum number of connections in the pool
            connection_pool (Any, optional): Pre-configured connection pool
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.use_azure_credential = use_azure_credential
        self.ssl_ca = ssl_ca
        self.ssl_disabled = ssl_disabled
        self.connection_pool = connection_pool

        # Handle Azure authentication
        if use_azure_credential:
            if not AZURE_IDENTITY_AVAILABLE:
                raise ImportError(
                    "Azure Identity is required for Azure credential authentication. "
                    "Please install it using 'pip install azure-identity'"
                )
            self._setup_azure_auth()

        # Setup connection pool
        if self.connection_pool is None:
            self._setup_connection_pool(minconn, maxconn)

        # Create collection if it doesn't exist
        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col(name=collection_name, vector_size=embedding_model_dims, distance="cosine")

    def _setup_azure_auth(self):
        """Setup Azure authentication using DefaultAzureCredential."""
        try:
            credential = DefaultAzureCredential()
            # Get access token for Azure Database for MySQL
            token = credential.get_token("https://ossrdbms-aad.database.windows.net/.default")
            # Use token as password
            self.password = token.token
            logger.info("Successfully authenticated using Azure DefaultAzureCredential")
        except Exception as e:
            logger.error(f"Failed to authenticate with Azure: {e}")
            raise

    def _setup_connection_pool(self, minconn: int, maxconn: int):
        """Setup MySQL connection pool."""
        connect_kwargs = {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "autocommit": False,
        }

        # SSL configuration
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
                **connect_kwargs
            )
            logger.info("Successfully created MySQL connection pool")
        except Exception as e:
            logger.error(f"Failed to create connection pool: {e}")
            raise

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        """
        Context manager to get a cursor from the connection pool.
        Auto-commits or rolls back based on exception.
        """
        conn = self.connection_pool.connection()
        cur = conn.cursor()
        try:
            yield cur
            if commit:
                conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.error(f"Database error: {exc}", exc_info=True)
            raise
        finally:
            cur.close()
            conn.close()

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table in MySQL).
        Enables vector extension and creates appropriate indexes.

        Args:
            name (str, optional): Collection name (uses self.collection_name if not provided)
            vector_size (int, optional): Vector dimension (uses self.embedding_model_dims if not provided)
            distance (str): Distance metric (cosine, euclidean, dot_product)
        """
        table_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        with self._get_cursor(commit=True) as cur:
            # Create table with vector column
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS `{table_name}` (
                    id VARCHAR(255) PRIMARY KEY,
                    vector JSON,
                    payload JSON,
                    INDEX idx_payload_keys ((CAST(payload AS CHAR(255)) ARRAY))
                )
            """)
            logger.info(f"Created collection '{table_name}' with vector dimension {dims}")

    def insert(self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None):
        """
        Insert vectors into the collection.

        Args:
            vectors (List[List[float]]): List of vectors to insert
            payloads (List[Dict], optional): List of payloads corresponding to vectors
            ids (List[str], optional): List of IDs corresponding to vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        data = []
        for vector, payload, vec_id in zip(vectors, payloads, ids):
            data.append((vec_id, json.dumps(vector), json.dumps(payload)))

        with self._get_cursor(commit=True) as cur:
            cur.executemany(
                f"INSERT INTO `{self.collection_name}` (id, vector, payload) VALUES (%s, %s, %s) "
                f"ON DUPLICATE KEY UPDATE vector = VALUES(vector), payload = VALUES(payload)",
                data
            )

    def _cosine_distance(self, vec1_json: str, vec2: List[float]) -> str:
        """Generate SQL for cosine distance calculation."""
        # For MySQL, we need to calculate cosine similarity manually
        # This is a simplified version - in production, you'd use stored procedures or UDFs
        return """
            1 - (
                (SELECT SUM(a.val * b.val) /
                (SQRT(SUM(a.val * a.val)) * SQRT(SUM(b.val * b.val))))
                FROM (
                    SELECT JSON_EXTRACT(vector, CONCAT('$[', idx, ']')) as val
                    FROM (SELECT @row := @row + 1 as idx FROM (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3) t1, (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3) t2) indices
                    WHERE idx < JSON_LENGTH(vector)
                ) a,
                (
                    SELECT JSON_EXTRACT(%s, CONCAT('$[', idx, ']')) as val
                    FROM (SELECT @row := @row + 1 as idx FROM (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3) t1, (SELECT 0 UNION ALL SELECT 1 UNION ALL SELECT 2 UNION ALL SELECT 3) t2) indices
                    WHERE idx < JSON_LENGTH(%s)
                ) b
                WHERE a.idx = b.idx
            )
        """

    def search(
        self,
        query: str,
        vectors: List[float],
        limit: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using cosine similarity.

        Args:
            query (str): Query string (not used in vector search)
            vectors (List[float]): Query vector
            limit (int): Number of results to return
            filters (Dict, optional): Filters to apply to the search

        Returns:
            List[OutputData]: Search results
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("JSON_EXTRACT(payload, %s) = %s")
                filter_params.extend([f"$.{k}", json.dumps(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        # For simplicity, we'll compute cosine similarity in Python
        # In production, you'd want to use MySQL stored procedures or UDFs
        with self._get_cursor() as cur:
            query_sql = f"""
                SELECT id, vector, payload
                FROM `{self.collection_name}`
                {filter_clause}
            """
            cur.execute(query_sql, filter_params)
            results = cur.fetchall()

        # Calculate cosine similarity in Python
        import numpy as np
        query_vec = np.array(vectors)
        scored_results = []

        for row in results:
            vec = np.array(json.loads(row['vector']))
            # Cosine similarity
            similarity = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
            distance = 1 - similarity
            scored_results.append((row['id'], distance, row['payload']))

        # Sort by distance and limit
        scored_results.sort(key=lambda x: x[1])
        scored_results = scored_results[:limit]

        return [
            OutputData(id=r[0], score=float(r[1]), payload=json.loads(r[2]) if isinstance(r[2], str) else r[2])
            for r in scored_results
        ]

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete
        """
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DELETE FROM `{self.collection_name}` WHERE id = %s", (vector_id,))

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ):
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update
            vector (List[float], optional): Updated vector
            payload (Dict, optional): Updated payload
        """
        with self._get_cursor(commit=True) as cur:
            if vector is not None:
                cur.execute(
                    f"UPDATE `{self.collection_name}` SET vector = %s WHERE id = %s",
                    (json.dumps(vector), vector_id),
                )
            if payload is not None:
                cur.execute(
                    f"UPDATE `{self.collection_name}` SET payload = %s WHERE id = %s",
                    (json.dumps(payload), vector_id),
                )

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve

        Returns:
            OutputData: Retrieved vector or None if not found
        """
        with self._get_cursor() as cur:
            cur.execute(
                f"SELECT id, vector, payload FROM `{self.collection_name}` WHERE id = %s",
                (vector_id,),
            )
            result = cur.fetchone()
            if not result:
                return None
            return OutputData(
                id=result['id'],
                score=None,
                payload=json.loads(result['payload']) if isinstance(result['payload'], str) else result['payload']
            )

    def list_cols(self) -> List[str]:
        """
        List all collections (tables).

        Returns:
            List[str]: List of collection names
        """
        with self._get_cursor() as cur:
            cur.execute("SHOW TABLES")
            return [row[f"Tables_in_{self.database}"] for row in cur.fetchall()]

    def delete_col(self):
        """Delete the collection (table)."""
        with self._get_cursor(commit=True) as cur:
            cur.execute(f"DROP TABLE IF EXISTS `{self.collection_name}`")
        logger.info(f"Deleted collection '{self.collection_name}'")

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information
        """
        with self._get_cursor() as cur:
            cur.execute("""
                SELECT
                    TABLE_NAME as name,
                    TABLE_ROWS as count,
                    ROUND(((DATA_LENGTH + INDEX_LENGTH) / 1024 / 1024), 2) as size_mb
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            """, (self.database, self.collection_name))
            result = cur.fetchone()

        if result:
            return {
                "name": result['name'],
                "count": result['count'],
                "size": f"{result['size_mb']} MB"
            }
        return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100
    ) -> List[List[OutputData]]:
        """
        List all vectors in the collection.

        Args:
            filters (Dict, optional): Filters to apply
            limit (int): Number of vectors to return

        Returns:
            List[List[OutputData]]: List of vectors
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("JSON_EXTRACT(payload, %s) = %s")
                filter_params.extend([f"$.{k}", json.dumps(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self._get_cursor() as cur:
            cur.execute(
                f"""
                SELECT id, vector, payload
                FROM `{self.collection_name}`
                {filter_clause}
                LIMIT %s
                """,
                (*filter_params, limit)
            )
            results = cur.fetchall()

        return [[
            OutputData(
                id=r['id'],
                score=None,
                payload=json.loads(r['payload']) if isinstance(r['payload'], str) else r['payload']
            ) for r in results
        ]]

    def reset(self):
        """Reset the collection by deleting and recreating it."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(name=self.collection_name, vector_size=self.embedding_model_dims)

    def __del__(self):
        """Close the connection pool when the object is deleted."""
        try:
            if hasattr(self, 'connection_pool') and self.connection_pool:
                self.connection_pool.close()
        except Exception:
            pass
