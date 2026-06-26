import json
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster
except ImportError:
    raise ImportError(
        "Apache Cassandra vector store requires cassandra-driver. "
        "Please install it using 'pip install cassandra-driver'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]{0,127}$')

DISTANCE_METRIC_MAP = {
    "cosine": "COSINE",
    "euclidean": "EUCLIDEAN",
    "dot_product": "DOT_PRODUCT",
}


def _validate_identifier(name: str, label: str = "identifier") -> str:
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}': only letters, digits, and underscores are allowed, "
            "must start with a letter or underscore, and be at most 128 characters."
        )
    return name


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
        self.contact_points = contact_points
        self.port = port
        self.username = username
        self.password = password
        self.keyspace = _validate_identifier(keyspace, "keyspace")
        self.collection_name = _validate_identifier(collection_name, "collection_name")
        self.embedding_model_dims = embedding_model_dims
        self.secure_connect_bundle = secure_connect_bundle
        self.protocol_version = protocol_version
        self.load_balancing_policy = load_balancing_policy

        self.cluster = None
        self.session = None
        self._setup_connection()

        self._create_keyspace()
        self._create_table()

    def _setup_connection(self):
        try:
            auth_provider = None
            if self.username and self.password:
                auth_provider = PlainTextAuthProvider(
                    username=self.username,
                    password=self.password
                )

            if self.secure_connect_bundle:
                self.cluster = Cluster(
                    cloud={'secure_connect_bundle': self.secure_connect_bundle},
                    auth_provider=auth_provider,
                    protocol_version=self.protocol_version
                )
            else:
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
        try:
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
        try:
            query = f"""
                CREATE TABLE IF NOT EXISTS {self.keyspace}.{self.collection_name} (
                    id text PRIMARY KEY,
                    vector VECTOR<FLOAT, {self.embedding_model_dims}>,
                    payload text
                )
            """
            self.session.execute(query)

            index_name = f"{self.collection_name}_vector_idx"
            index_query = f"""
                CREATE CUSTOM INDEX IF NOT EXISTS {index_name}
                ON {self.keyspace}.{self.collection_name} (vector)
                USING 'StorageAttachedIndex'
                WITH OPTIONS = {{'similarity_function': 'COSINE'}}
            """
            self.session.execute(index_query)
            logger.info(f"Table '{self.collection_name}' with SAI vector index is ready")
        except Exception as e:
            logger.error(f"Failed to create table: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        table_name = _validate_identifier(name, "table_name") if name else self.collection_name
        dims = vector_size or self.embedding_model_dims
        similarity_function = DISTANCE_METRIC_MAP.get(distance, "COSINE")

        try:
            query = f"""
                CREATE TABLE IF NOT EXISTS {self.keyspace}.{table_name} (
                    id text PRIMARY KEY,
                    vector VECTOR<FLOAT, {dims}>,
                    payload text
                )
            """
            self.session.execute(query)

            index_name = f"{table_name}_vector_idx"
            index_query = f"""
                CREATE CUSTOM INDEX IF NOT EXISTS {index_name}
                ON {self.keyspace}.{table_name} (vector)
                USING 'StorageAttachedIndex'
                WITH OPTIONS = {{'similarity_function': '{similarity_function}'}}
            """
            self.session.execute(index_query)
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
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        try:
            query_cql = f"""
                SELECT id, payload, similarity_cosine(vector, ?) AS score
                FROM {self.keyspace}.{self.collection_name}
                ORDER BY vector ANN OF ?
                LIMIT ?
            """
            prepared = self.session.prepare(query_cql)
            rows = self.session.execute(prepared, (vectors, vectors, top_k))

            results = []
            for row in rows:
                payload = json.loads(row.payload) if row.payload else {}

                if filters:
                    match = all(payload.get(k) == v for k, v in filters.items())
                    if not match:
                        continue

                score = row.score if row.score is not None else 0.0
                results.append(
                    OutputData(
                        id=row.id,
                        score=float(score),
                        payload=payload
                    )
                )

            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id: str):
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
        try:
            prepared = self.session.prepare(
                "SELECT table_name FROM system_schema.tables WHERE keyspace_name = ?"
            )
            rows = self.session.execute(prepared, (self.keyspace,))
            return [row.table_name for row in rows]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_col(self):
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
        try:
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
        top_k: int = 100
    ) -> List[List[OutputData]]:
        try:
            query = f"""
                SELECT id, vector, payload
                FROM {self.keyspace}.{self.collection_name}
                LIMIT {top_k}
            """
            rows = self.session.execute(query)

            results = []
            for row in rows:
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
        try:
            if self.cluster:
                self.cluster.shutdown()
                logger.info("Cassandra cluster connection closed")
        except Exception:
            pass
