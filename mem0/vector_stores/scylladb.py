import json
import logging
import re
import ssl
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel

try:
    from cassandra.auth import PlainTextAuthProvider
    from cassandra.cluster import Cluster
    from cassandra.policies import DCAwareRoundRobinPolicy
except ImportError:
    raise ImportError(
        "ScyllaDB vector store requires scylla-driver. Please install it using 'pip install scylla-driver'"
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")

_INDEX_BUILDING_RE = re.compile(r"is not available yet|missing index", re.IGNORECASE)

# The vector index builds asynchronously in the background after CREATE
# CUSTOM INDEX returns, so it can reject ANN queries with a transient error
# for a short time right after creation -- either a 503 ("... is not
# available yet ...") or a 404 ("missing index: ...") depending on which
# node serves the query.
_INDEX_READY_TIMEOUT_SECONDS = 30
_INDEX_READY_POLL_INTERVAL_SECONDS = 1

# Mem0 scopes every memory by these ids. They are stored as dedicated columns
# (copied from the payload) so that ANN search and listing can be restricted
# to a single user/agent/run on the server instead of post-filtering globally.
_ENTITY_KEYS = ("user_id", "agent_id", "run_id")

# ScyllaDB rejects ANN queries with LIMIT > 1000.
_MAX_ANN_LIMIT = 1000

_LIST_FETCH_SIZE = 1000

_SUPPORTED_OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a CQL identifier and normalize it to lowercase.

    Unquoted CQL identifiers are case-insensitive and stored in lowercase, while
    the driver quotes names in some calls (e.g. ``set_keyspace``). Normalizing
    here keeps every statement and schema lookup referring to the same object.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}': only letters, digits, and underscores are allowed, "
            "must start with a letter or underscore, and be at most 128 characters."
        )
    return name.lower()


def _compare(actual: Any, op: str, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op in ("in", "nin"):
        if not isinstance(expected, list):
            raise ValueError(f"Filter operator {op!r} requires a list value, got {type(expected).__name__}")
        return (actual in expected) == (op == "in")
    if op in ("contains", "icontains"):
        if not isinstance(actual, str):
            return False
        if op == "icontains":
            return str(expected).lower() in actual.lower()
        return str(expected) in actual
    try:
        actual_num, expected_num = float(actual), float(expected)
    except (TypeError, ValueError):
        return False
    if op == "gt":
        return actual_num > expected_num
    if op == "gte":
        return actual_num >= expected_num
    if op == "lt":
        return actual_num < expected_num
    return actual_num <= expected_num


def _matches_filters(payload: Dict[str, Any], filters: Optional[Dict[str, Any]]) -> bool:
    """Evaluate Mem0 filters (simple, operator and logical forms) against a payload."""
    if not filters:
        return True

    for key, value in filters.items():
        if key in ("$or", "OR"):
            if not any(_matches_filters(payload, sub) for sub in value):
                return False
        elif key in ("$not", "NOT"):
            if any(_matches_filters(payload, sub) for sub in value):
                return False
        elif key in ("$and", "AND"):
            if not all(_matches_filters(payload, sub) for sub in value):
                return False
        elif value == "*":
            if key not in payload:
                return False
        elif isinstance(value, dict):
            unsupported = set(value) - _SUPPORTED_OPERATORS
            if unsupported:
                raise ValueError(f"Unsupported filter operator(s) for key {key!r}: {', '.join(sorted(unsupported))}")
            if key not in payload:
                return False
            if not all(_compare(payload[key], op, expected) for op, expected in value.items()):
                return False
        elif isinstance(value, list):
            if payload.get(key) not in value:
                return False
        elif key not in payload or payload[key] != value:
            return False

    return True


def _split_entity_filters(filters: Optional[Dict[str, Any]]) -> Tuple[Dict[str, str], Dict[str, Any]]:
    """Split filters into server-side entity equality filters and remaining payload filters."""
    entity_filters: Dict[str, str] = {}
    payload_filters: Dict[str, Any] = {}
    for key, value in (filters or {}).items():
        if key in _ENTITY_KEYS and isinstance(value, (str, int)) and not isinstance(value, bool) and value != "*":
            entity_filters[key] = str(value)
        else:
            payload_filters[key] = value
    return entity_filters, payload_filters


def _entity_values(payload: Dict[str, Any]) -> Tuple[Optional[str], ...]:
    return tuple(str(payload[key]) if payload.get(key) is not None else None for key in _ENTITY_KEYS)


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
        replication_factor: int = 3,
    ):
        """
        Initialize the ScyllaDB vector store.

        Uses ScyllaDB Vector Search local vector indexes keyed on user_id,
        agent_id and run_id, so every ANN query is confined to a single
        user/agent/run instead of searching across all tenants.

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
            replication_factor: Replication factor used when creating the keyspace (default: 3)
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
        self.replication_factor = replication_factor

        self.cluster = None
        self.session = None
        self._setup_connection()
        self._create_keyspace()
        self.create_col()

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
                cluster_kwargs["load_balancing_policy"] = DCAwareRoundRobinPolicy(local_dc=self.datacenter)

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
                f"CREATE KEYSPACE IF NOT EXISTS {self.keyspace} "
                f"WITH REPLICATION = {{'class': 'NetworkTopologyStrategy', "
                f"'replication_factor': {int(self.replication_factor)}}}"
            )
            logger.info(f"Keyspace '{self.keyspace}' is ready")
        except Exception as e:
            logger.error(f"Failed to create keyspace: {e}")
            raise

    def _table(self, table_name: Optional[str] = None) -> str:
        return f"{self.keyspace}.{table_name or self.collection_name}"

    def _wait_for_index_ready(self, table_name: str, dims: int):
        """
        Block until every local vector index on *table_name* can serve ANN queries.

        The indexes build asynchronously after CREATE CUSTOM INDEX returns, so
        querying them immediately can fail with a transient 503 ("... is not
        available yet ..."). Polling a cheap ANN query per index here means
        callers of insert()/search() never have to handle that transient state.
        """
        probe_vector = [0.0] * dims
        deadline = time.monotonic() + _INDEX_READY_TIMEOUT_SECONDS
        for key in _ENTITY_KEYS:
            probe = self.session.prepare(
                f"SELECT id FROM {self._table(table_name)} WHERE {key} = ? ORDER BY vector ANN OF ? LIMIT 1"
            )
            while True:
                try:
                    self.session.execute(probe, ("", probe_vector))
                    break
                except Exception as e:
                    if not _INDEX_BUILDING_RE.search(str(e)) or time.monotonic() >= deadline:
                        raise
                    time.sleep(_INDEX_READY_POLL_INTERVAL_SECONDS)

    def create_col(self, name: str = None, vector_size: int = None, distance: str = "cosine"):
        """
        Create a collection (table + indexes) in ScyllaDB if it does not already exist.

        Schema::

            id text PRIMARY KEY, vector VECTOR<FLOAT, N>,
            user_id text, agent_id text, run_id text, payload text

        One local vector index per entity column scopes ANN search to a single
        user/agent/run (requires ScyllaDB 2026.3+ for local indexes keyed on
        non-primary-key columns). Secondary indexes on the same columns let
        list() read only the matching rows.

        Args:
            name: Collection name (uses self.collection_name if not provided)
            vector_size: Vector dimension (uses self.embedding_model_dims if not provided)
            distance: Distance metric — only 'cosine' is supported
        """
        table_name = _validate_identifier(name, "table_name") if name else self.collection_name
        dims = vector_size or self.embedding_model_dims
        table = self._table(table_name)

        try:
            # ScyllaDB requires a fixed-width VECTOR<FLOAT, N> type for ANN search.
            self.session.execute(
                f"CREATE TABLE IF NOT EXISTS {table} ("
                f"id text PRIMARY KEY, "
                f"vector VECTOR<FLOAT, {dims}>, "
                f"user_id text, "
                f"agent_id text, "
                f"run_id text, "
                f"payload text"
                f")"
            )
            for key in _ENTITY_KEYS:
                others = ", ".join(k for k in _ENTITY_KEYS if k != key)
                # Local vector index: a separate ANN index per distinct entity id.
                # The other entity columns are filtering columns for combined scopes.
                self.session.execute(
                    f"CREATE CUSTOM INDEX IF NOT EXISTS {table_name}_{key}_ann "
                    f"ON {table} (({key}), vector, {others}) "
                    f"USING 'vector_index' "
                    f"WITH OPTIONS = {{'similarity_function': 'COSINE'}}"
                )
                self.session.execute(f"CREATE INDEX IF NOT EXISTS {table_name}_{key}_idx ON {table} ({key})")
            self._wait_for_index_ready(table_name, dims)
            logger.info(f"Collection '{table_name}' with vector dimension {dims} is ready")
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
        if payloads is None:
            payloads = [{} for _ in vectors]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in vectors]
        if not (len(vectors) == len(payloads) == len(ids)):
            raise ValueError(
                f"vectors, payloads and ids must have the same length (got {len(vectors)}, {len(payloads)}, {len(ids)})"
            )

        logger.info(f"Inserting {len(vectors)} vectors into '{self.collection_name}'")
        # Serialize everything up front so a bad payload fails before any row is written.
        rows = [
            (vec_id, vector, *_entity_values(payload), json.dumps(payload))
            for vec_id, vector, payload in zip(ids, vectors, payloads)
        ]

        try:
            prepared = self.session.prepare(
                f"INSERT INTO {self._table()} (id, vector, user_id, agent_id, run_id, payload) VALUES (?, ?, ?, ?, ?, ?)"
            )
            for row in rows:
                self.session.execute(prepared, row)
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
        Search for the most similar vectors within a user/agent/run scope.

        user_id / agent_id / run_id equality filters are pushed into the ANN
        query, so it only searches that scope's local vector index. Any other
        filters are evaluated against the payload; if they remove candidates,
        the query is repeated with a larger LIMIT until top_k matches are found
        or the scope is exhausted.

        Args:
            query: Query string (not used directly; the embedding vector is used)
            vectors: Query embedding vector
            top_k: Maximum number of results to return
            filters: Mem0 filters; must include at least one of user_id, agent_id, run_id

        Returns:
            List of OutputData sorted by descending cosine similarity (higher = more similar)
        """
        entity_filters, payload_filters = _split_entity_filters(filters)
        if not entity_filters:
            raise ValueError(
                "ScyllaDB search requires at least one of user_id, agent_id or run_id in filters, "
                "because vector search is scoped per user/agent/run via local vector indexes."
            )

        where = " AND ".join(f"{key} = ?" for key in entity_filters)
        # Filtering on more than one entity column inside a local index requires ALLOW FILTERING;
        # it only filters rows within the selected user/agent/run partition.
        allow_filtering = " ALLOW FILTERING" if len(entity_filters) > 1 else ""
        top_k = min(top_k, _MAX_ANN_LIMIT)

        try:
            prepared = self.session.prepare(
                f"SELECT id, similarity_cosine(vector, ?) AS score, payload "
                f"FROM {self._table()} WHERE {where} "
                f"ORDER BY vector ANN OF ? LIMIT ?{allow_filtering}"
            )

            fetch_limit = top_k
            while True:
                rows = list(self.session.execute(prepared, (vectors, *entity_filters.values(), vectors, fetch_limit)))
                results: List[OutputData] = []
                for row in rows:
                    payload = json.loads(row.payload) if row.payload else {}
                    if not _matches_filters(payload, payload_filters):
                        continue
                    results.append(OutputData(id=row.id, score=row.score, payload=payload))
                    if len(results) == top_k:
                        break

                scope_exhausted = len(rows) < fetch_limit
                if len(results) == top_k or scope_exhausted or fetch_limit >= _MAX_ANN_LIMIT:
                    return results
                fetch_limit = min(fetch_limit * 4, _MAX_ANN_LIMIT)
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
            prepared = self.session.prepare(f"DELETE FROM {self._table()} WHERE id = ?")
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
        Update a vector's embedding and/or payload in a single statement.

        Args:
            vector_id: ID of the record to update
            vector: New embedding vector (skipped if None)
            payload: New payload dict (skipped if None)
        """
        assignments: List[str] = []
        values: List[Any] = []
        if vector is not None:
            assignments.append("vector = ?")
            values.append(vector)
        if payload is not None:
            # Serialize before touching the database so a bad payload leaves the row unchanged.
            serialized = json.dumps(payload)
            assignments.extend(f"{key} = ?" for key in _ENTITY_KEYS)
            values.extend(_entity_values(payload))
            assignments.append("payload = ?")
            values.append(serialized)
        if not assignments:
            return

        try:
            prepared = self.session.prepare(f"UPDATE {self._table()} SET {', '.join(assignments)} WHERE id = ?")
            self.session.execute(prepared, (*values, vector_id))
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
            OutputData, or None if the record does not exist
        """
        try:
            prepared = self.session.prepare(f"SELECT id, payload FROM {self._table()} WHERE id = ?")
            row = self.session.execute(prepared, (vector_id,)).one()
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            raise
        if not row:
            return None
        return OutputData(id=row.id, score=None, payload=json.loads(row.payload) if row.payload else {})

    def list_cols(self) -> List[str]:
        """List all table names in the current keyspace."""
        try:
            prepared = self.session.prepare("SELECT table_name FROM system_schema.tables WHERE keyspace_name = ?")
            rows = self.session.execute(prepared, (self.keyspace,))
            return [row.table_name for row in rows]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            raise

    def delete_col(self):
        """Drop the current collection (table and its indexes)."""
        try:
            self.session.execute(f"DROP TABLE IF EXISTS {self._table()}")
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """Return basic metadata about the current collection."""
        try:
            row = self.session.execute(f"SELECT COUNT(*) AS count FROM {self._table()}").one()
        except Exception as e:
            logger.error(f"Failed to get collection info: {e}")
            raise
        return {
            "name": self.collection_name,
            "keyspace": self.keyspace,
            "count": row.count if row else 0,
            "vector_dims": self.embedding_model_dims,
        }

    def list(
        self,
        filters: Optional[Dict] = None,
        top_k: Optional[int] = 100,
    ) -> List[List[OutputData]]:
        """
        Retrieve up to *top_k* records matching *filters*.

        user_id / agent_id / run_id equality filters are resolved server-side via
        secondary indexes. Results are read page by page and other filters are
        applied to each payload, so *top_k* is applied after filtering.

        Args:
            filters: Optional Mem0 filters
            top_k: Maximum number of records to return (None for no limit)

        Returns:
            A list containing a single inner list of OutputData objects
        """
        entity_filters, payload_filters = _split_entity_filters(filters)
        cql = f"SELECT id, payload FROM {self._table()}"
        if entity_filters:
            cql += " WHERE " + " AND ".join(f"{key} = ?" for key in entity_filters)
            if len(entity_filters) > 1:
                cql += " ALLOW FILTERING"

        try:
            bound = self.session.prepare(cql).bind(tuple(entity_filters.values()))
            bound.fetch_size = _LIST_FETCH_SIZE
            results: List[OutputData] = []
            for row in self.session.execute(bound):
                payload = json.loads(row.payload) if row.payload else {}
                if not _matches_filters(payload, payload_filters):
                    continue
                results.append(OutputData(id=row.id, score=None, payload=payload))
                if top_k is not None and len(results) >= top_k:
                    break
            return [results]
        except Exception as e:
            logger.error(f"Failed to list vectors: {e}")
            raise

    def reset(self):
        """
        Reset the current collection by dropping and recreating the table and indexes.

        TRUNCATE is intentionally avoided: it does not propagate to the CDC log,
        so the vector index would retain all previously indexed vectors in memory.
        Dropping and recreating both the table and the custom indexes is the only
        correct way to fully clear vector index state.
        """
        try:
            logger.warning(f"Resetting collection '{self.collection_name}'…")
            self.delete_col()
            self.create_col()
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
