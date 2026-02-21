"""
ClickZetta Vector Store Implementation

ClickZetta is a cloud-native data lakehouse platform that supports vector storage and search.

Usage:
    from mem0 import Memory

    config = {
        "vector_store": {
            "provider": "clickzetta",
            "config": {
                "collection_name": "mem0_memories",
                "service": "your-service",
                "instance": "your-instance",
                "workspace": "your-workspace",
                "schema": "your-schema",
                "username": "your-username",
                "password": "your-password",
                "vcluster": "your-vcluster"
            }
        }
    }
    m = Memory.from_config(config)

Dependencies:
    pip install clickzetta-connector-python
"""

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

try:
    import clickzetta.dbapi as clickzetta_dbapi
except ImportError:
    raise ImportError(
        "The 'clickzetta-connector-python' library is required. "
        "Please install it using 'pip install clickzetta-connector-python'."
    )


class OutputData(BaseModel):
    """Search result output data model."""
    id: str
    score: float
    payload: Optional[Dict[str, Any]] = None


class ClickZetta(VectorStoreBase):
    """
    ClickZetta Vector Store Implementation.
    
    Uses ClickZetta's SQL interface to store and query vector data.
    Vectors are stored as VECTOR type, using cosine similarity for search by default.
    """

    def __init__(
        self,
        collection_name: str,
        embedding_model_dims: int,
        service: str,
        instance: str,
        workspace: str,
        schema: str,
        username: str,
        password: str,
        vcluster: str,
        distance_metric: str = "cosine",
        protocol: str = "http",
    ):
        """
        Initialize ClickZetta Vector Store.

        Args:
            collection_name: Collection/table name.
            embedding_model_dims: Embedding vector dimensions.
            service: ClickZetta service name.
            instance: Instance name.
            workspace: Workspace name.
            schema: Schema name.
            username: Username.
            password: Password.
            vcluster: Virtual cluster name.
            distance_metric: Distance metric (cosine, euclidean, dot_product).
            protocol: Gateway protocol.
        """
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.distance_metric = distance_metric
        
        # Connection configuration
        self.service = service
        self.instance = instance
        self.workspace = workspace
        self.schema = schema
        self.username = username
        self.password = password
        self.vcluster = vcluster
        self.protocol = protocol
        
        # Create connection
        self.connection = self._create_connection()
        
        # Create collection table
        self.create_col(embedding_model_dims, distance_metric)

    def _create_connection(self):
        """Create database connection."""
        try:
            conn = clickzetta_dbapi.connect(
                service=self.service,
                instance=self.instance,
                workspace=self.workspace,
                schema=self.schema,
                username=self.username,
                password=self.password,
                vcluster=self.vcluster,
                protocol=self.protocol
            )
            logger.info("Successfully connected to ClickZetta")
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to ClickZetta: {e}")
            raise

    def _execute_query(self, query: str, params: dict = None) -> List[tuple]:
        """Execute SQL query."""
        cursor = self.connection.cursor()
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # For SELECT queries, return results
            if query.strip().upper().startswith("SELECT"):
                return cursor.fetchall()
        except Exception as e:
            logger.error(f"Query execution failed: {e}, SQL: {query}")
            raise
        finally:
            cursor.close()

    def create_col(self, vector_size: int, distance: str = "cosine"):
        """
        Create vector storage table.

        Args:
            vector_size: Vector dimensions.
            distance: Distance metric.
        """
        # Check if table already exists
        check_query = f"""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = '{self.schema}' 
            AND table_name = '{self.collection_name}'
        """
        
        try:
            result = self._execute_query(check_query)
            if result and result[0][0] > 0:
                logger.debug(f"Collection {self.collection_name} already exists. Skipping creation.")
                return
        except Exception:
            pass  # Table may not exist, continue to create
        
        # Create table
        create_query = f"""
            CREATE TABLE IF NOT EXISTS {self.schema}.{self.collection_name} (
                id VARCHAR(64) PRIMARY KEY,
                vector vector({vector_size}),
                payload JSON,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        
        try:
            self._execute_query(create_query)
            logger.info(f"Created collection {self.collection_name}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def insert(self, vectors: List[List[float]], payloads: List[Dict] = None, ids: List[str] = None):
        """
        Insert vector data.

        Args:
            vectors: List of vectors.
            payloads: List of metadata.
            ids: List of IDs.
        """
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]
        
        if payloads is None:
            payloads = [{} for _ in range(len(vectors))]
        
        logger.info(f"Inserting {len(vectors)} vectors into collection {self.collection_name}")
        
        for i, (vec_id, vector, payload) in enumerate(zip(ids, vectors, payloads)):
            # Convert vector to array string format
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            payload_json = json.dumps(payload, ensure_ascii=False)

            param = {'hints': {'cz.sql.insert.duplicate.key.policy': 'update'}}
            
            query = f"""
                INSERT INTO {self.schema}.{self.collection_name} (id, vector, payload) 
                VALUES ('{vec_id}', cast("{vector_str}" as vector(384)), json_parse('{payload_json}'))
            """
            
            try:
                self._execute_query(query, param)
            except Exception as e:
                logger.error(f"Failed to insert vector {vec_id}: {e}, SQL: {query}")
                raise

    def _build_distance_expression(self, query_vector: List[float]) -> str:
        """
        Build distance calculation expression.

        Args:
            query_vector: Query vector.

        Returns:
            SQL distance calculation expression.
        """
        vector_str = "[" + ",".join(str(v) for v in query_vector) + "]"
        
        if self.distance_metric == "cosine":
            return f'cosine_distance(vector, cast("{vector_str}" as vector({self.embedding_model_dims})))'
        elif self.distance_metric == "euclidean":
            return f'L2_distance(vector, cast("{vector_str}" as vector({self.embedding_model_dims})))'
        elif self.distance_metric == "dot_product":
            return f'(-1 * dot_product(vector, cast("{vector_str}" as vector({self.embedding_model_dims}))))'
        else:
            return f'cosine_distance(vector, cast("{vector_str}" as vector({self.embedding_model_dims})))'

    def _build_filter_clause(self, filters: Dict) -> str:
        """
        Build filter condition SQL.

        Args:
            filters: Filter condition dictionary.

        Returns:
            WHERE clause string.
        """
        if not filters:
            return ""
        
        conditions = []
        for key, value in filters.items():
            if isinstance(value, dict) and "gte" in value and "lte" in value:
                # Range query
                conditions.append(
                    f"json_extract_string(payload, '$.{key}') >= {value['gte']} "
                    f"AND json_extract_string(payload, '$.{key}') <= {value['lte']}"
                )
            elif isinstance(value, str):
                conditions.append(f"json_extract_string(payload, '$.{key}') = '{value}'")
            else:
                conditions.append(f"json_extract_string(payload, '$.{key}') = {value}")
        
        return " AND " + " AND ".join(conditions) if conditions else ""

    def search(self, query: str, vectors: List[float], limit: int = 5, filters: Dict = None) -> List[OutputData]:
        """
        Search for similar vectors.

        Args:
            query: Query text (unused, kept for interface compatibility).
            vectors: Query vector.
            limit: Number of results to return.
            filters: Filter conditions.

        Returns:
            List of search results.
        """
        distance_expr = self._build_distance_expression(vectors)
        filter_clause = self._build_filter_clause(filters)
        
        search_query = f"""
            SELECT id, payload, {distance_expr} AS distance
            FROM {self.schema}.{self.collection_name}
            WHERE 1=1 {filter_clause}
            ORDER BY distance ASC
            LIMIT {limit}
        """
        
        try:
            results = self._execute_query(search_query)
            
            output = []
            for row in results:
                vec_id, payload_str, distance = row[0], row[1], row[2]
                
                try:
                    payload = json.loads(payload_str) if payload_str else {}
                except json.JSONDecodeError:
                    payload = {}
                
                # Convert distance to similarity score
                if self.distance_metric == "cosine":
                    # cosine_distance range [0, 2] -> score [1, 0]
                    score = 1 - float(distance) / 2
                elif self.distance_metric == "euclidean":
                    # Smaller distance means higher score, range (0, 1]
                    score = 1 / (1 + float(distance))
                else:  # dot_product
                    # Restore to positive dot product value
                    score = -float(distance)
                
                output.append(OutputData(id=vec_id, score=score, payload=payload))
            
            return output
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id: str):
        """
        Delete a vector.

        Args:
            vector_id: Vector ID.
        """
        query = f"""
            DELETE FROM {self.schema}.{self.collection_name}
            WHERE id = '{vector_id}'
        """
        self._execute_query(query)
        logger.debug(f"Deleted vector {vector_id}")

    def update(self, vector_id: str, vector: List[float] = None, payload: Dict = None):
        """
        Update vector and metadata.

        Args:
            vector_id: Vector ID.
            vector: New vector.
            payload: New metadata.
        """
        updates = []
        
        if vector is not None:
            vector_str = "[" + ",".join(str(v) for v in vector) + "]"
            updates.append(f"vector = ARRAY{vector_str}")
        
        if payload is not None:
            payload_json = json.dumps(payload, ensure_ascii=False)
            updates.append(f"payload = '{payload_json}'")
        
        if not updates:
            return
        
        query = f"""
            UPDATE {self.schema}.{self.collection_name}
            SET {", ".join(updates)}
            WHERE id = '{vector_id}'
        """
        self._execute_query(query)
        logger.debug(f"Updated vector {vector_id}")

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a single vector.

        Args:
            vector_id: Vector ID.

        Returns:
            Vector data, or None if not found.
        """
        query = f"""
            SELECT id, vector, payload
            FROM {self.schema}.{self.collection_name}
            WHERE id = '{vector_id}'
        """
        
        results = self._execute_query(query)
        
        if not results:
            return None
        
        row = results[0]
        vec_id, vector, payload_str = row[0], row[1], row[2]
        
        try:
            payload = json.loads(payload_str) if payload_str else {}
        except json.JSONDecodeError:
            payload = {}
        
        return OutputData(id=vec_id, score=1.0, payload=payload)

    def list_cols(self) -> List[str]:
        """
        List all collections (tables).

        Returns:
            List of collection names.
        """
        query = f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = '{self.schema}'
        """
        
        results = self._execute_query(query)
        return [row[0] for row in results]

    def delete_col(self):
        """Delete the current collection."""
        query = f"DROP TABLE IF EXISTS {self.schema}.{self.collection_name}"
        self._execute_query(query)
        logger.info(f"Deleted collection {self.collection_name}")

    def col_info(self) -> Dict:
        """
        Get collection information.

        Returns:
            Collection metadata.
        """
        # Get row count
        count_query = f"SELECT COUNT(*) FROM {self.schema}.{self.collection_name}"
        count_result = self._execute_query(count_query)
        row_count = count_result[0][0] if count_result else 0
        
        return {
            "name": self.collection_name,
            "schema": self.schema,
            "row_count": row_count,
            "embedding_dims": self.embedding_model_dims,
            "distance_metric": self.distance_metric,
        }

    def list(self, filters: Dict = None, limit: int = 100) -> List[OutputData]:
        """
        List all vectors in the collection.

        Args:
            filters: Filter conditions.
            limit: Maximum number of results.

        Returns:
            List of vectors.
        """
        filter_clause = self._build_filter_clause(filters)
        
        query = f"""
            SELECT id, payload
            FROM {self.schema}.{self.collection_name}
            WHERE 1=1 {filter_clause}
            LIMIT {limit}
        """
        
        results = self._execute_query(query)
        
        output = []
        for row in results:
            vec_id, payload_str = row[0], row[1]
            
            try:
                payload = json.loads(payload_str) if payload_str else {}
            except json.JSONDecodeError:
                payload = {}
            
            output.append(OutputData(id=vec_id, score=1.0, payload=payload))
        
        return output

    def reset(self):
        """Reset the collection (delete and recreate)."""
        logger.warning(f"Resetting collection {self.collection_name}...")
        self.delete_col()
        self.create_col(self.embedding_model_dims, self.distance_metric)

    def __del__(self):
        """Close database connection."""
        if hasattr(self, 'connection') and self.connection:
            try:
                self.connection.close()
            except Exception:
                pass
