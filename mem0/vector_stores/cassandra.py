import json
import logging
import uuid
from typing import Any, Dict, List, Optional

import numpy as np
from pydantic import BaseModel

try:
    from cassandra.cluster import Cluster
    from cassandra.auth import PlainTextAuthProvider
except ImportError:
    raise ImportError(
        "Apache Cassandra vector store requires cassandra-driver. "
        "Please install it using 'pip install cassandra-driver'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class CassandraDB(VectorStoreBase):
    def __init__(
        self,
        contact_points: List[str],
        port: int = 9042,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keyspace: str = "mem0",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        secure_connect_bundle: Optional[str] = None,
        protocol_version: int = 4,
        load_balancing_policy: Optional[Any] = None,
    ):
        """
        Initialize the Apache Cassandra vector store.

        Args:
            contact_points (List[str]): List of contact point addresses (e.g., ['127.0.0.1'])
            port (int): Cassandra port (default: 9042)
            username (str, optional): Database username
            password (str, optional): Database password
            keyspace (str): Keyspace name (default: "mem0")
            collection_name (str): Table name (default: "memories")
            embedding_model_dims (int): Dimension of the embedding vector (default: 1536)
            secure_connect_bundle (str, optional): Path to secure connect bundle for Astra DB
            protocol_version (int): CQL protocol version (default: 4)
            load_balancing_policy (Any, optional): Custom load balancing policy
        """
        self.contact_points = contact_points
        self.port = port
        self.username = username
        self.password = password
        self.keyspace = keyspace
        self.collection_name = collection_name
        self.embedding_model_dims = embedding_model_dims
        self.secure_connect_bundle = secure_connect_bundle
        self.protocol_version = protocol_version
        self.load_balancing_policy = load_balancing_policy

        # Initialize connection
        self.cluster = None
        self.session = None
        self._setup_connection()
        
        # Create keyspace and table if they don't exist
        self._create_keyspace()
        self._create_table()

    def _setup_connection(self):
        """Setup Cassandra cluster connection."""
        try:
            # Setup authentication
            auth_provider = None
            if self.username and self.password:
                auth_provider = PlainTextAuthProvider(
                    username=self.username,
                    password=self.password
                )

            # Connect to Astra DB using secure connect bundle
            if self.secure_connect_bundle:
                self.cluster = Cluster(
                    cloud={'secure_connect_bundle': self.secure_connect_bundle},
                    auth_provider=auth_provider,
                    protocol_version=self.protocol_version
                )
            else:
                # Connect to standard Cassandra cluster
                cluster_kwargs = {
                    'contact_points': self.contact_points,
                    'port': self.port,
                    'protocol_version': self.protocol_version
                }
                
                if auth_provider:
                    cluster_kwargs['auth_provider'] = auth_provider
                
                if self.load_balancing_policy:
                    cluster_kwargs['load_balancing_policy'] = self.load_balancing_policy

                self.cluster = Cluster(**cluster_kwargs)

            self.session = self.cluster.connect()
            logger.info("Successfully connected to Cassandra cluster")
        except Exception as e:
            logger.error(f"Failed to connect to Cassandra: {e}")
            raise

    def _create_keyspace(self):
        """Create keyspace if it doesn't exist."""
        try:
            # Use SimpleStrategy for single datacenter, NetworkTopologyStrategy for production
            query = f"""
                CREATE KEYSPACE IF NOT EXISTS {self.keyspace}
                WITH replication = {{'class': 'SimpleStrategy', 'replication_factor': 1}}
            """
            self.session.execute(query)
            self.session.set_keyspace(self.keyspace)
            logger.info(f"Keyspace '{self.keyspace}' is ready")
        except Exception as e:
            logger.error(f"Failed to create keyspace: {e}")
            raise

    def _create_table(self):
        """Create table with vector column if it doesn't exist."""
        try:
            # Create table with vector stored as list<float> and payload as text (JSON)
            query = f"""
                CREATE TABLE IF NOT EXISTS {self.keyspace}.{self.collection_name} (
                    id text PRIMARY KEY,
                    vector list<float>,
                    payload text
                )
            """
            self.session.execute(query)
            logger.info(f"Table '{self.collection_name}' is ready")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table in Cassandra).

        Args:
            name (str, optional): Collection name (uses self.collection_name if not provided)
            vector_size (int, optional): Vector dimension (uses self.embedding_model_dims if not provided)
            distance (str): Distance metric (cosine, euclidean, dot_product)
        """
        table_name = name or self.collection_name
        dims = vector_size or self.embedding_model_dims

        try:
            query = f"""
                CREATE TABLE IF NOT EXISTS {self.keyspace}.{table_name} (
                    id text PRIMARY KEY,
                    vector list<float>,
                    payload text
                )
            """
            self.session.execute(query)
            logger.info(f"Created collection '{table_name}' with vector dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None
    ):
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
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            query = f"""
                INSERT INTO {self.keyspace}.{self.collection_name} (id, vector, payload)
                VALUES (?, ?, ?)
            """
            prepared = self.session.prepare(query)

            for vector, payload, vec_id in zip(vectors, payloads, ids):
                self.session.execute(
                    prepared,
                    (vec_id, vector, json.dumps(payload))
                )
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
            # Fetch all vectors (in production, you'd want pagination or filtering)
            query_cql = f"""
                SELECT id, vector, payload
                FROM {self.keyspace}.{self.collection_name}
            """
            rows = self.session.execute(query_cql)

            # Calculate cosine similarity in Python
            query_vec = np.array(vectors)
            scored_results = []

            for row in rows:
                if not row.vector:
                    continue

                vec = np.array(row.vector)
                
                # Cosine similarity
                similarity = np.dot(query_vec, vec) / (np.linalg.norm(query_vec) * np.linalg.norm(vec))
                distance = 1 - similarity

                # Apply filters if provided
                if filters:
                    try:
                        payload = json.loads(row.payload) if row.payload else {}
                        match = all(payload.get(k) == v for k, v in filters.items())
                        if not match:
                            continue
                    except json.JSONDecodeError:
                        continue

                scored_results.append((row.id, distance, row.payload))

            # Sort by distance and limit
            scored_results.sort(key=lambda x: x[1])
            scored_results = scored_results[:limit]

            return [
                OutputData(
                    id=r[0],
                    score=float(r[1]),
                    payload=json.loads(r[2]) if r[2] else {}
                )
                for r in scored_results
            ]
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
            query = f"""
                DELETE FROM {self.keyspace}.{self.collection_name}
                WHERE id = ?
            """
            prepared = self.session.prepare(query)
            self.session.execute(prepared, (vector_id,))
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
            if vector is not None:
                query = f"""
                    UPDATE {self.keyspace}.{self.collection_name}
                    SET vector = ?
                    WHERE id = ?
                """
                prepared = self.session.prepare(query)
                self.session.execute(prepared, (vector, vector_id))

            if payload is not None:
                query = f"""
                    UPDATE {self.keyspace}.{self.collection_name}
                    SET payload = ?
                    WHERE id = ?
                """
                prepared = self.session.prepare(query)
                self.session.execute(prepared, (json.dumps(payload), vector_id))

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
            query = f"""
                SELECT id, vector, payload
                FROM {self.keyspace}.{self.collection_name}
                WHERE id = ?
            """
            prepared = self.session.prepare(query)
            row = self.session.execute(prepared, (vector_id,)).one()

            if not row:
                return None

            return OutputData(
                id=row.id,
                score=None,
                payload=json.loads(row.payload) if row.payload else {}
            )
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    def list_cols(self) -> List[str]:
        """
        List all collections (tables in the keyspace).

        Returns:
            List[str]: List of collection names
        """
        try:
            query = f"""
                SELECT table_name
                FROM system_schema.tables
                WHERE keyspace_name = '{self.keyspace}'
            """
            rows = self.session.execute(query)
            return [row.table_name for row in rows]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_col(self):
        """Delete the collection (table)."""
        try:
            query = f"""
                DROP TABLE IF EXISTS {self.keyspace}.{self.collection_name}
            """
            self.session.execute(query)
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """
        Get information about the collection.

        Returns:
            Dict[str, Any]: Collection information
        """
        try:
            # Get row count (approximate)
            query = f"""
                SELECT COUNT(*) as count
                FROM {self.keyspace}.{self.collection_name}
            """
            row = self.session.execute(query).one()
            count = row.count if row else 0

            return {
                "name": self.collection_name,
                "keyspace": self.keyspace,
                "count": count,
                "vector_dims": self.embedding_model_dims
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
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
        try:
            query = f"""
                SELECT id, vector, payload
                FROM {self.keyspace}.{self.collection_name}
                LIMIT {limit}
            """
            rows = self.session.execute(query)

            results = []
            for row in rows:
                # Apply filters if provided
                if filters:
                    try:
                        payload = json.loads(row.payload) if row.payload else {}
                        match = all(payload.get(k) == v for k, v in filters.items())
                        if not match:
                            continue
                    except json.JSONDecodeError:
                        continue

                results.append(
                    OutputData(
                        id=row.id,
                        score=None,
                        payload=json.loads(row.payload) if row.payload else {}
                    )
                )

            return [results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            return [[]]

    def reset(self):
        """Reset the collection by truncating it."""
        try:
            logger.warning(f"Resetting collection {self.collection_name}...")
            query = f"""
                TRUNCATE TABLE {self.keyspace}.{self.collection_name}
            """
            self.session.execute(query)
            logger.info(f"Collection '{self.collection_name}' has been reset")
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise

    def __del__(self):
        """Close the cluster connection when the object is deleted."""
        try:
            if self.cluster:
                self.cluster.shutdown()
                logger.info("Cassandra cluster connection closed")
        except Exception:
            pass

