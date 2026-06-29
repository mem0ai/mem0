import json
import logging
import re
import ssl
import uuid
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

try:
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy
except ImportError:
    raise ImportError(
        "ScyllaDB vector store requires scylla-driver. "
        "Please install it using 'pip install scylla-driver'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")


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


class ScyllaDB(VectorStoreBase):
    def __init__(
        self,
        contact_points: List[str],
        port: int = 9042,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keyspace: str = "mem0",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        datacenter: Optional[str] = None,
        use_ssl: bool = False,
        ssl_cert_path: Optional[str] = None,
    ):
        """
        Initialize the ScyllaDB vector store.

        Uses ScyllaDB's native SAI vector index for ANN (Approximate Nearest Neighbor)
        search, which is far more efficient than loading all vectors into memory.

        Args:
            contact_points: List of contact point addresses (e.g., ['node-0.aws-us-east-1.x.clusters.scylla.cloud'])
            port: ScyllaDB CQL port (default: 9042)
            username: Database username
            password: Database password
            keyspace: Keyspace name (default: "mem0")
            collection_name: Table name (default: "memories")
            embedding_model_dims: Dimension of the embedding vector (default: 1536)
            datacenter: Local datacenter name for DC-aware routing (recommended for ScyllaDB Cloud)
            use_ssl: Enable SSL/TLS
            ssl_cert_path: Path to a CA certificate file for SSL verification.
                           Pass None to use the system's default CA bundle.
        """
        self.contact_points = contact_points
        self.port = port
        self.username = username
        self.password = password
        self.keyspace = _validate_identifier(keyspace, "keyspace")
        self.collection_name = _validate_identifier(collection_name, "collection_name")
        self.embedding_model_dims = embedding_model_dims
        self.datacenter = datacenter
        self.use_ssl = use_ssl
        self.ssl_cert_path = ssl_cert_path

        self.cluster = None
        self.session = None
        self._setup_connection()
        self._create_keyspace()
        self._create_table()

    def _build_ssl_context(self) -> ssl.SSLContext:
        """Build an SSL context for ScyllaDB Cloud connections."""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True
        if self.ssl_cert_path:
            context.load_verify_locations(cafile=self.ssl_cert_path)
        else:
            context.load_default_certs()
        return context

    def _setup_connection(self):
        """Set up the ScyllaDB cluster connection."""
        try:
            auth_provider = None
            if self.username and self.password:
                auth_provider = PlainTextAuthProvider(
                    username=self.username,
                    password=self.password,
                )

            cluster_kwargs: Dict[str, Any] = {
                "contact_points": self.contact_points,
                "port": self.port,
            }

            if auth_provider:
                cluster_kwargs["auth_provider"] = auth_provider

            if self.datacenter:
                cluster_kwargs["load_balancing_policy"] = DCAwareRoundRobinPolicy(
                    local_dc=self.datacenter
                )

            if self.use_ssl:
                cluster_kwargs["ssl_context"] = self._build_ssl_context()

            self.cluster = Cluster(**cluster_kwargs)
            self.session = self.cluster.connect()
            logger.info("Successfully connected to ScyllaDB cluster")
        except Exception as e:
            logger.error(f"Failed to connect to ScyllaDB: {e}")
            raise

    def _create_keyspace(self):
        """Create the keyspace if it does not already exist."""
        try:
            self.session.execute(
                f"CREATE KEYSPACE IF NOT EXISTS {self.keyspace}"
            )
            self.session.set_keyspace(self.keyspace)
            logger.info(f"Keyspace '{self.keyspace}' is ready")
        except Exception as e:
            logger.error(f"Failed to create keyspace: {e}")
            raise

    def _create_table(self):
        """Create the table and SAI vector index if they do not already exist."""
        try:
            # ScyllaDB requires a fixed-width VECTOR<FLOAT, N> type for ANN search.
            self.session.execute(
                f"CREATE TABLE IF NOT EXISTS {self.keyspace}.{self.collection_name} ("
                f"    id text PRIMARY KEY,"
                f"    vector VECTOR<FLOAT, {self.embedding_model_dims}>,"
                f"    payload text"
                f")"
            )

            # Vector index enables server-side ANN search.
            self.session.execute(
                f"CREATE CUSTOM INDEX IF NOT EXISTS ON "
                f"{self.keyspace}.{self.collection_name} (vector) "
                f"USING 'vector_index' "
                f"WITH OPTIONS = {{'similarity_function': 'COSINE'}}"
            )
            logger.info(f"Table '{self.collection_name}' and SAI index are ready")
        except Exception as e:
            logger.error(f"Failed to create table or index: {e}")
            raise

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a new collection (table + SAI index) in ScyllaDB.

        Args:
            name: Collection name (uses self.collection_name if not provided)
            vector_size: Vector dimension (uses self.embedding_model_dims if not provided)
            distance: Distance metric — only 'cosine' is supported by the SAI index
        """
        table_name = _validate_identifier(name, "table_name") if name else self.collection_name
        dims = vector_size or self.embedding_model_dims

        try:
            self.session.execute(
                f"CREATE TABLE IF NOT EXISTS {self.keyspace}.{table_name} ("
                f"    id text PRIMARY KEY,"
                f"    vector VECTOR<FLOAT, {dims}>,"
                f"    payload text"
                f")"
            )
            self.session.execute(
                f"CREATE CUSTOM INDEX IF NOT EXISTS ON "
                f"{self.keyspace}.{table_name} (vector) "
                f"USING 'vector_index' "
                f"WITH OPTIONS = {{'similarity_function': 'COSINE'}}"
            )
            logger.info(f"Created collection '{table_name}' with vector dimension {dims}")
        except Exception as e:
            logger.error(f"Failed to create collection: {e}")
            raise

    def insert(
        self,
        vectors: List[List[float]],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ):
        """
        Insert vectors into the collection.

        Args:
            vectors: List of embedding vectors to insert
            payloads: Optional metadata dicts corresponding to each vector
            ids: Optional string IDs; auto-generated (UUID) when not provided
        """
        logger.info(f"Inserting {len(vectors)} vectors into '{self.collection_name}'")

        if payloads is None:
            payloads = [{}] * len(vectors)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(len(vectors))]

        try:
            prepared = self.session.prepare(
                f"INSERT INTO {self.keyspace}.{self.collection_name} (id, vector, payload) "
                f"VALUES (?, ?, ?)"
            )
            for vec_id, vector, payload in zip(ids, vectors, payloads):
                self.session.execute(prepared, (vec_id, vector, json.dumps(payload)))
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
        """
        Search for the most similar vectors using ScyllaDB's native ANN index.

        Filters are applied post-retrieval because CQL WHERE clauses on non-indexed
        payload columns cannot be pushed through the ANN ORDER BY path.

        Args:
            query: Query string (not used directly; the embedding vector is used)
            vectors: Query embedding vector
            top_k: Maximum number of results to return
            filters: Optional key/value filters applied against the payload dict

        Returns:
            List of OutputData sorted by ascending cosine distance
        """
        try:
            # Fetch extra rows when filtering so we can still return top_k after pruning.
            fetch_limit = top_k * 10 if filters else top_k

            prepared = self.session.prepare(
                f"SELECT id, similarity_cosine(vector, ?) AS score, payload "
                f"FROM {self.keyspace}.{self.collection_name} "
                f"ORDER BY vector ANN OF ? "
                f"LIMIT ?"
            )
            rows = self.session.execute(prepared, (vectors, vectors, fetch_limit))

            results: List[OutputData] = []
            for row in rows:
                if filters:
                    try:
                        payload = json.loads(row.payload) if row.payload else {}
                        if not all(payload.get(k) == v for k, v in filters.items()):
                            continue
                    except json.JSONDecodeError:
                        continue

                results.append(
                    OutputData(
                        id=row.id,
                        # ANN returns cosine similarity (higher = more similar).
                        # Mem0 expects distance (lower = more similar), so invert.
                        score=float(1.0 - row.score) if row.score is not None else None,
                        payload=json.loads(row.payload) if row.payload else {},
                    )
                )
                if len(results) == top_k:
                    break

            return results
        except Exception as e:
            logger.error(f"Search failed: {e}")
            raise

    def delete(self, vector_id: str):
        """
        Delete a single vector by ID.

        Args:
            vector_id: ID of the vector to delete
        """
        try:
            prepared = self.session.prepare(
                f"DELETE FROM {self.keyspace}.{self.collection_name} WHERE id = ?"
            )
            self.session.execute(prepared, (vector_id,))
            logger.info(f"Deleted vector '{vector_id}'")
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
        Update a vector's embedding and/or payload.

        Args:
            vector_id: ID of the record to update
            vector: New embedding vector (skipped if None)
            payload: New payload dict (skipped if None)
        """
        try:
            if vector is not None:
                prepared = self.session.prepare(
                    f"UPDATE {self.keyspace}.{self.collection_name} "
                    f"SET vector = ? WHERE id = ?"
                )
                self.session.execute(prepared, (vector, vector_id))

            if payload is not None:
                prepared = self.session.prepare(
                    f"UPDATE {self.keyspace}.{self.collection_name} "
                    f"SET payload = ? WHERE id = ?"
                )
                self.session.execute(prepared, (json.dumps(payload), vector_id))

            logger.info(f"Updated vector '{vector_id}'")
        except Exception as e:
            logger.error(f"Failed to update vector: {e}")
            raise

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a single vector by ID.

        Args:
            vector_id: ID of the vector to retrieve

        Returns:
            OutputData or None if the record does not exist
        """
        try:
            prepared = self.session.prepare(
                f"SELECT id, payload FROM {self.keyspace}.{self.collection_name} WHERE id = ?"
            )
            row = self.session.execute(prepared, (vector_id,)).one()
            if not row:
                return None

            return OutputData(
                id=row.id,
                score=None,
                payload=json.loads(row.payload) if row.payload else {},
            )
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            return None

    def list_cols(self) -> List[str]:
        """List all table names in the current keyspace."""
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
        """Drop the current collection (table)."""
        try:
            self.session.execute(
                f"DROP TABLE IF EXISTS {self.keyspace}.{self.collection_name}"
            )
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """Return basic metadata about the current collection."""
        try:
            row = self.session.execute(
                f"SELECT COUNT(*) AS count FROM {self.keyspace}.{self.collection_name}"
            ).one()
            return {
                "name": self.collection_name,
                "keyspace": self.keyspace,
                "count": row.count if row else 0,
                "vector_dims": self.embedding_model_dims,
            }
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            return {}

    def list(
        self,
        filters: Optional[Dict] = None,
        top_k: int = 100,
    ) -> List[List[OutputData]]:
        """
        Retrieve up to *top_k* records, optionally filtered by payload fields.

        Args:
            filters: Optional key/value filters applied against the payload dict
            top_k: Maximum number of records to return

        Returns:
            A list containing a single inner list of OutputData objects
        """
        try:
            rows = self.session.execute(
                f"SELECT id, payload FROM {self.keyspace}.{self.collection_name} LIMIT {top_k}"
            )
            results: List[OutputData] = []
            for row in rows:
                if filters:
                    try:
                        payload = json.loads(row.payload) if row.payload else {}
                        if not all(payload.get(k) == v for k, v in filters.items()):
                            continue
                    except json.JSONDecodeError:
                        continue

                results.append(
                    OutputData(
                        id=row.id,
                        score=None,
                        payload=json.loads(row.payload) if row.payload else {},
                    )
                )

            return [results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            return [[]]

    def reset(self):
        """
        Reset the current collection by dropping and recreating the table and index.

        TRUNCATE is intentionally avoided: it does not propagate to the CDC log,
        so the vector index would retain all previously indexed vectors in memory.
        Dropping and recreating both the table and the custom index is the only
        correct way to fully clear vector index state.
        """
        try:
            logger.warning(f"Resetting collection '{self.collection_name}'…")
            self.session.execute(
                f"DROP TABLE IF EXISTS {self.keyspace}.{self.collection_name}"
            )
            self._create_table()
            logger.info(f"Collection '{self.collection_name}' has been reset")
        except Exception as e:
            logger.error(f"Failed to reset collection: {e}")
            raise

    def __del__(self):
        """Shut down the cluster connection when the object is garbage-collected."""
        try:
            if self.cluster:
                self.cluster.shutdown()
                logger.info("ScyllaDB cluster connection closed")
        except Exception:
            pass
