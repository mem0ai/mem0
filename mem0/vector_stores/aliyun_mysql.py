import json
import logging
from contextlib import contextmanager
from typing import Any, List, Optional

from pydantic import BaseModel

try:
    import mysql.connector
except ImportError as e:
    raise ImportError(
        "mysql.connector is not available. Please install it using 'pip install mysql-connector-python'"
    ) from e

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class MySQLVector(VectorStoreBase):
    def __init__(
        self,
        dbname,
        collection_name,
        embedding_model_dims,
        user,
        password,
        host,
        port,
        distance_function="euclidean",
        m_value=16,
        ssl_disabled=False,
        ssl_ca=None,
        ssl_cert=None,
        ssl_key=None,
        connection_string=None,
        charset="utf8mb4",
        autocommit=True,
    ):
        """
        Initialize the Aliyun MySQL Vector database.

        Args:
            dbname (str): Database name
            collection_name (str): Collection name
            embedding_model_dims (int): Dimension of the embedding vector
            user (str): Database user
            password (str): Database password
            host (str): Database host
            port (int): Database port
            distance_function (str): Distance function for vector index ('euclidean' or 'cosine')
            m_value (int): M parameter for HNSW index (3-200). Higher values = more accurate but slower
            ssl_disabled (bool): Disable SSL connection
            ssl_ca (str, optional): SSL CA certificate file path
            ssl_cert (str, optional): SSL certificate file path
            ssl_key (str, optional): SSL key file path
            connection_string (str, optional): Aliyun MySQL connection string (overrides individual connection parameters)
            charset (str): Character set for the connection
            autocommit (bool): Enable autocommit mode
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_function = distance_function
        self.m_value = m_value
        
        # Connection parameters
        if connection_string:
            # Parse connection string (simplified parsing)
            # Format: mysql://user:password@host:port/database
            import urllib.parse
            parsed = urllib.parse.urlparse(connection_string)
            self.connection_params = {
                'user': parsed.username,
                'password': parsed.password,
                'host': parsed.hostname,
                'port': parsed.port or 3306,
                'database': parsed.path.lstrip('/') or dbname,
                'charset': charset,
                'autocommit': autocommit,
            }
        else:
            self.connection_params = {
                'user': user,
                'password': password,
                'host': host,
                'port': port or 3306,
                'database': dbname,
                'charset': charset,
                'autocommit': autocommit,
            }

        # SSL configuration
        if not ssl_disabled:
            ssl_config = {}
            if ssl_ca:
                ssl_config['ca'] = ssl_ca
            if ssl_cert:
                ssl_config['cert'] = ssl_cert
            if ssl_key:
                ssl_config['key'] = ssl_key
            if ssl_config:
                self.connection_params['ssl'] = ssl_config

        # Test connection and create collection if needed
        collections = self.list_cols()
        if collection_name not in collections:
            self.create_col()

    @contextmanager
    def _get_connection(self):
        """
        Context manager to get a database connection.
        """
        conn = None
        try:
            conn = mysql.connector.connect(**self.connection_params)
            yield conn
        except Exception as e:
            logger.error(f"Database connection error: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                conn.close()


    def create_col(self) -> None:
        """
        Create a new collection (table in Aliyun MySQL).
        Will also initialize vector search index.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Create table with VECTOR column
                cursor.execute(f"""
                    CREATE TABLE IF NOT EXISTS {self.collection_name} (
                        id VARCHAR(255) PRIMARY KEY,
                        embedding VECTOR({self.embedding_model_dims}) NOT NULL,
                        payload JSON,
                        VECTOR INDEX (embedding) M={self.m_value} DISTANCE={self.distance_function}
                    )
                """)
                conn.commit()
                logger.info(f"Created collection {self.collection_name} with vector index")
            except Exception as e:
                logger.error(f"Error creating collection: {e}")
                raise
            finally:
                cursor.close()

    def insert(self, vectors: List[List[float]], payloads=None, ids=None) -> None:
        """
        Insert vectors into the collection.
        
        Args:
            vectors: List of vectors to insert
            payloads: List of payload dictionaries
            ids: List of IDs for the vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        
        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            import uuid
            ids = [str(uuid.uuid4()) for _ in vectors]

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Insert vectors one by one using VEC_FromText function
                for vector_id, vector, payload in zip(ids, vectors, payloads):
                    # Convert vector to string format for VEC_FromText
                    vector_str = '[' + ','.join(map(str, vector)) + ']'
                    payload_json = json.dumps(payload) if payload else None
                    
                    cursor.execute(f"""
                        INSERT INTO {self.collection_name} (id, embedding, payload) 
                        VALUES (%s, VEC_FromText(%s), %s)
                    """, (vector_id, vector_str, payload_json))
                
                conn.commit()
            except Exception as e:
                logger.error(f"Error inserting vectors: {e}")
                conn.rollback()
                raise
            finally:
                cursor.close()

    def search(
        self,
        query: str,
        vectors: List[float],
        limit: Optional[int] = 5,
        filters: Optional[dict] = None,
    ) -> List[OutputData]:
        """
        Search for similar vectors using Aliyun MySQL Vector distance functions.

        Args:
            query (str): Query string (for logging)
            vectors (List[float]): Query vector
            limit (int, optional): Number of results to return. Defaults to 5.
            filters (Dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results.
        """
        filter_conditions = []
        filter_params = []

        if filters:
            for k, v in filters.items():
                filter_conditions.append("JSON_EXTRACT(payload, %s) = %s")
                filter_params.extend([f"$.{k}", str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        # Convert query vector to string format for VEC_FromText
        query_vector_str = '[' + ','.join(map(str, vectors)) + ']'

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Use VEC_DISTANCE function which automatically uses the appropriate distance function
                if filter_conditions:
                    query_params = [query_vector_str] + filter_params + [limit]
                else:
                    query_params = [query_vector_str, limit]
                
                logger.debug(f"SQL query: SELECT id, VEC_DISTANCE_EUCLIDEAN(embedding, VEC_FromText(%s)) AS distance, payload FROM {self.collection_name} {filter_clause} ORDER BY distance LIMIT %s")
                logger.debug(f"Query params: {query_params}")
                
                cursor.execute(f"""
                    SELECT id, VEC_DISTANCE_EUCLIDEAN(embedding, VEC_FromText(%s)) AS distance, payload
                    FROM {self.collection_name}
                    {filter_clause}
                    ORDER BY distance
                    LIMIT %s
                """, query_params)

                results = cursor.fetchall()
                return [
                    OutputData(
                        id=str(r[0]), 
                        score=float(r[1]), 
                        payload=json.loads(r[2]) if r[2] else {}
                    ) 
                    for r in results
                ]
            except Exception as e:
                logger.error(f"Error searching vectors: {e}")
                raise
            finally:
                cursor.close()

    def delete(self, vector_id: str) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"DELETE FROM {self.collection_name} WHERE id = %s", (vector_id,))
                conn.commit()
            except Exception as e:
                logger.error(f"Error deleting vector: {e}")
                raise
            finally:
                cursor.close()

    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[dict] = None,
    ) -> None:
        """
        Update a vector and its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector.
            payload (Dict, optional): Updated payload.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                if vector:
                    vector_str = '[' + ','.join(map(str, vector)) + ']'
                    cursor.execute(
                        f"UPDATE {self.collection_name} SET embedding = VEC_FromText(%s) WHERE id = %s",
                        (vector_str, vector_id),
                    )
                if payload:
                    cursor.execute(
                        f"UPDATE {self.collection_name} SET payload = %s WHERE id = %s",
                        (json.dumps(payload), vector_id),
                    )
                conn.commit()
            except Exception as e:
                logger.error(f"Error updating vector: {e}")
                conn.rollback()
                raise
            finally:
                cursor.close()

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            OutputData: Retrieved vector data or None if not found.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(
                    f"SELECT id, embedding, payload FROM {self.collection_name} WHERE id = %s",
                    (vector_id,),
                )
                result = cursor.fetchone()
                if not result:
                    return None
                
                payload = json.loads(result[2]) if result[2] else {}
                return OutputData(id=str(result[0]), score=None, payload=payload)
            except Exception as e:
                logger.error(f"Error retrieving vector: {e}")
                raise
            finally:
                cursor.close()

    def list_cols(self) -> List[str]:
        """
        List all collections (tables).

        Returns:
            List[str]: List of collection names.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SHOW TABLES")
                return [row[0] for row in cursor.fetchall()]
            except Exception as e:
                logger.error(f"Error listing collections: {e}")
                raise
            finally:
                cursor.close()

    def delete_col(self) -> None:
        """Delete the collection (table)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {self.collection_name}")
                conn.commit()
                logger.info(f"Deleted collection {self.collection_name}")
            except Exception as e:
                logger.error(f"Error deleting collection: {e}")
                raise
            finally:
                cursor.close()

    def col_info(self) -> dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {self.collection_name}")
                row_count = cursor.fetchone()[0]
                
                # Get table size information
                cursor.execute(f"""
                    SELECT 
                        table_name,
                        ROUND(((data_length + index_length) / 1024 / 1024), 2) AS total_size_mb
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() AND table_name = %s
                """, (self.collection_name,))
                
                result = cursor.fetchone()
                size_mb = result[1] if result else 0
                
                return {
                    "name": self.collection_name,
                    "count": row_count,
                    "size": f"{size_mb} MB"
                }
            except Exception as e:
                logger.error(f"Error getting collection info: {e}")
                raise
            finally:
                cursor.close()

    def list(
        self,
        filters: Optional[dict] = None,
        limit: Optional[int] = 100
    ) -> List[OutputData]:
        """
        List all vectors in the collection.

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
                filter_conditions.append("JSON_EXTRACT(payload, %s) = %s")
                filter_params.extend([f"$.{k}", str(v)])

        filter_clause = "WHERE " + " AND ".join(filter_conditions) if filter_conditions else ""

        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(f"""
                    SELECT id, embedding, payload
                    FROM {self.collection_name}
                    {filter_clause}
                    LIMIT %s
                """, (*filter_params, limit))
                
                results = cursor.fetchall()
                return [
                    OutputData(
                        id=str(r[0]), 
                        score=None, 
                        payload=json.loads(r[2]) if r[2] else {}
                    ) 
                    for r in results
                ]
            except Exception as e:
                logger.error(f"Error listing vectors: {e}")
                raise
            finally:
                cursor.close()

    def reset(self) -> None:
        """Reset the collection by deleting and recreating it."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col()
