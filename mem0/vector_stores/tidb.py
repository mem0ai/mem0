import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    import pymysql
    from pymysql.cursors import DictCursor
except ImportError:
    raise ImportError(
        "TiDB Vector store requires pymysql. "
        "Please install it using 'pip install pymysql'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class TiDBVector(VectorStoreBase):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 4000,
        user: str = "root",
        password: str = "",
        database: str = "mem0",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        **kwargs
    ):
        """
        Initialize the TiDB Vector store.

        Args:
            host (str): TiDB server host
            port (int): TiDB server port
            user (str): Database username
            password (str): Database password
            database (str): Database name
            collection_name (str): Table name for storing vectors
            embedding_model_dims (int): Dimension of the embedding vector
            **kwargs: Additional arguments passed to pymysql
        """
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.database = database
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.kwargs = kwargs

        # Initialize TiDB connection
        self.connection = None
        self._setup_connection()
        
        # Create table if it doesn't exist
        self._create_table()

    def _setup_connection(self):
        """Setup TiDB connection."""
        try:
            self.connection = pymysql.connect(
                host=self.host,
                port=self.port,
                user=self.user,
                password=self.password,
                database=self.database,
                cursorclass=DictCursor,
                **self.kwargs
            )
            logger.info(f"Successfully connected to TiDB at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"Failed to connect to TiDB: {e}")
            raise

    def _create_table(self):
        """Create table if it doesn't exist."""
        try:
            with self.connection.cursor() as cursor:
                # Check if table exists
                cursor.execute(f"SHOW TABLES LIKE '{self.collection_name}'")
                if cursor.fetchone():
                    logger.info(f"Table '{self.collection_name}' already exists")
                else:
                    # Create table with vector column
                    create_table_sql = f"""
                    CREATE TABLE {self.collection_name} (
                        id VARCHAR(255) PRIMARY KEY,
                        vector JSON,
                        payload TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                    cursor.execute(create_table_sql)
                    self.connection.commit()
                    logger.info(f"Created table '{self.collection_name}' with vector dimension {self.embedding_model_dims}")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table in TiDB).

        Args:
            name (str, optional): Table name (uses self.collection_name if not provided)
            vector_size (int, optional): Vector dimension (uses self.embedding_model_dims if not provided)
            distance (str): Distance metric (cosine, euclidean, dot_product)
        """
        table_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        try:
            with self.connection.cursor() as cursor:
                # Check if table exists
                cursor.execute(f"SHOW TABLES LIKE '{table_name}'")
                if cursor.fetchone():
                    logger.info(f"Table '{table_name}' already exists")
                    return

                # Create table with vector column
                create_table_sql = f"""
                CREATE TABLE {table_name} (
                    id VARCHAR(255) PRIMARY KEY,
                    vector JSON,
                    payload TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
                """
                cursor.execute(create_table_sql)
                self.connection.commit()
                logger.info(f"Created table '{table_name}' with vector dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
        """
        Insert vectors into the table.

        Args:
            vectors (List[List[float]]): List of vectors to insert
            payloads (List[Dict], optional): List of payloads corresponding to vectors
            ids (List[str], optional): List of IDs corresponding to vectors
        """
        logger.info(f"Inserting {len(vectors)} vectors into table {self.collection_name}")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            with self.connection.cursor() as cursor:
                # Prepare data for insertion
                insert_data = []
                for vector, payload, vec_id in zip(vectors, payloads, ids):
                    insert_data.append((
                        vec_id,
                        json.dumps(vector),
                        json.dumps(payload)
                    ))

                # Insert data
                insert_sql = f"""
                INSERT INTO {self.collection_name} (id, vector, payload)
                VALUES (%s, %s, %s)
                ON DUPLICATE KEY UPDATE
                vector = VALUES(vector),
                payload = VALUES(payload),
                updated_at = CURRENT_TIMESTAMP
                """
                cursor.executemany(insert_sql, insert_data)
                self.connection.commit()
                logger.info(f"Successfully inserted {len(insert_data)} vectors")
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise

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
        try:
            with self.connection.cursor() as cursor:
                # Build filter conditions
                where_conditions = []
                params = []
                
                if filters:
                    for key, value in filters.items():
                        where_conditions.append(f"JSON_EXTRACT(payload, '$.{key}') = %s")
                        params.append(value)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                # Calculate cosine similarity using SQL
                # For simplicity, we'll use a basic vector similarity approach
                # In production, you might want to use TiDB's vector search capabilities
                search_sql = f"""
                SELECT id, vector, payload,
                       (
                           SELECT SUM(a.value * b.value)
                           FROM JSON_TABLE(vector, '$[*]' COLUMNS (value DOUBLE PATH '$')) a,
                                JSON_TABLE(%s, '$[*]' COLUMNS (value DOUBLE PATH '$')) b
                           WHERE a.ordinal = b.ordinal
                       ) / (
                           SQRT(
                               (SELECT SUM(value * value) FROM JSON_TABLE(vector, '$[*]' COLUMNS (value DOUBLE PATH '$')))
                           ) * SQRT(
                               (SELECT SUM(value * value) FROM JSON_TABLE(%s, '$[*]' COLUMNS (value DOUBLE PATH '$')))
                           )
                       ) as similarity
                FROM {self.collection_name}
                {where_clause}
                ORDER BY similarity DESC
                LIMIT %s
                """
                
                params = [json.dumps(vectors), json.dumps(vectors)] + params + [limit]
                cursor.execute(search_sql, params)
                results = cursor.fetchall()

                # Convert results to OutputData format
                output_results = []
                for row in results:
                    try:
                        payload = json.loads(row['payload']) if row['payload'] else {}
                    except json.JSONDecodeError:
                        payload = {}
                    
                    # Convert similarity to distance (1 - similarity)
                    similarity = float(row.get('similarity', 0.0))
                    distance = 1 - similarity if similarity <= 1 else 0.0
                    
                    output_results.append(OutputData(
                        id=row['id'],
                        score=float(distance),
                        payload=payload
                    ))

                return output_results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id: str):
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete
        """
        try:
            with self.connection.cursor() as cursor:
                delete_sql = f"DELETE FROM {self.collection_name} WHERE id = %s"
                cursor.execute(delete_sql, (vector_id,))
                self.connection.commit()
                logger.info(f"Deleted vector with id: {vector_id}")
        except Exception as e:
            logger.error(f"Failed to delete vector: {e}")
            raise

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
        try:
            with self.connection.cursor() as cursor:
                # Check if vector exists
                cursor.execute(f"SELECT id FROM {self.collection_name} WHERE id = %s", (vector_id,))
                if not cursor.fetchone():
                    logger.warning(f"Vector with id {vector_id} not found for update")
                    return

                # Prepare update data
                update_fields = []
                params = []
                
                if vector is not None:
                    update_fields.append("vector = %s")
                    params.append(json.dumps(vector))
                
                if payload is not None:
                    update_fields.append("payload = %s")
                    params.append(json.dumps(payload))
                
                if update_fields:
                    update_fields.append("updated_at = CURRENT_TIMESTAMP")
                    params.append(vector_id)
                    
                    update_sql = f"""
                    UPDATE {self.collection_name}
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    """
                    cursor.execute(update_sql, params)
                    self.connection.commit()
                    
                    logger.info(f"Updated vector with id: {vector_id}")
        except Exception as e:
            logger.error(f"Failed to update vector: {e}")
            raise

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector by ID.

        Args:
            vector_id (str): ID of the vector to retrieve

        Returns:
            OutputData: Retrieved vector or None if not found
        """
        try:
            with self.connection.cursor() as cursor:
                get_sql = f"SELECT id, vector, payload FROM {self.collection_name} WHERE id = %s"
                cursor.execute(get_sql, (vector_id,))
                row = cursor.fetchone()
                
                if not row:
                    return None

                try:
                    payload = json.loads(row['payload']) if row['payload'] else {}
                except json.JSONDecodeError:
                    payload = {}

                return OutputData(
                    id=row['id'],
                    score=None,
                    payload=payload
                )
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    def list_cols(self) -> List[str]:
        """
        List all tables (collections).

        Returns:
            List[str]: List of table names
        """
        try:
            with self.connection.cursor() as cursor:
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                return [table[f'Tables_in_{self.database}'] for table in tables]
        except Exception as e:
            logger.error(f"Failed to list tables: {e}")
            return []

    def delete_col(self):
        """Delete the table."""
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS {self.collection_name}")
                self.connection.commit()
                logger.info(f"Deleted table '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete table: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the table.

        Returns:
            Dict[str, Any]: Table information
        """
        try:
            with self.connection.cursor() as cursor:
                # Get table info
                cursor.execute(f"SELECT COUNT(*) as count FROM {self.collection_name}")
                count_result = cursor.fetchone()
                count = count_result['count'] if count_result else 0
                
                return {
                    "name": self.collection_name,
                    "count": count,
                    "vector_dims": self.embedding_model_dims,
                    "host": f"{self.host}:{self.port}"
                }
        except Exception as e:
            logger.error(f"Failed to get table info: {e}")
            return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        limit: int = 100
    ) -> List[List[OutputData]]:
        """
        List all vectors in the table.

        Args:
            filters (Dict, optional): Filters to apply
            limit (int): Number of vectors to return

        Returns:
            List[List[OutputData]]: List of vectors
        """
        try:
            with self.connection.cursor() as cursor:
                # Build filter conditions
                where_conditions = []
                params = []
                
                if filters:
                    for key, value in filters.items():
                        where_conditions.append(f"JSON_EXTRACT(payload, '$.{key}') = %s")
                        params.append(value)
                
                where_clause = ""
                if where_conditions:
                    where_clause = "WHERE " + " AND ".join(where_conditions)
                
                list_sql = f"""
                SELECT id, vector, payload
                FROM {self.collection_name}
                {where_clause}
                LIMIT %s
                """
                params.append(limit)
                cursor.execute(list_sql, params)
                results = cursor.fetchall()

                output_results = []
                for row in results:
                    try:
                        payload = json.loads(row['payload']) if row['payload'] else {}
                    except json.JSONDecodeError:
                        payload = {}

                    output_results.append(OutputData(
                        id=row['id'],
                        score=None,
                        payload=payload
                    ))

                return [output_results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            return [[]]

    def reset(self):
        """Reset the table by deleting and recreating it."""
        try:
            logger.warning(f"Resetting table {self.collection_name}...")
            self.delete_col()
            self._create_table()
            logger.info(f"Table '{self.collection_name}' has been reset")
        except Exception as e:
            logger.error(f"Failed to reset table: {e}")
            raise

    def __del__(self):
        """Cleanup when the object is deleted."""
        try:
            if self.connection:
                self.connection.close()
        except Exception:
            pass
