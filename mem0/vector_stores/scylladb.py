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
        "ScyllaDB vector store requires a CQL driver. "
        "Install either 'pip install cassandra-driver' (bundled with mem0's "
        "vector-stores extra) or 'pip install scylla-driver' (shard-aware, "
        "recommended for ScyllaDB). Do not install both: they share the same "
        "'cassandra' import package and overwrite each other."
    )

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_SAFE_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,127}$")

# The vector index builds asynchronously in the background after CREATE CUSTOM
# INDEX returns, so ANN queries can fail with a transient error for a short
# time right after creation (a 503 "... is not available yet ..." or a 404
# "missing index: ...", depending on which node serves the query).
_INDEX_BUILDING_RE = re.compile(r"is not available yet|missing index", re.IGNORECASE)
_INDEX_READY_TIMEOUT_SECONDS = 30
_INDEX_READY_POLL_INTERVAL_SECONDS = 1

# Upper bound for the progressive ANN window used when filters cannot be fully
# pushed down to the database. The window grows until enough matches are found
# or the table is exhausted; this cap only guards against pathological scans.
_MAX_SEARCH_WINDOW = 10_000

# Payload keys that are mirrored into dedicated table columns so they can be
# pushed down as equality predicates (scoped retrieval) instead of being
# evaluated client-side over the whole result set.
_SCOPE_FIELDS = ("user_id", "agent_id", "run_id")

# Filter operators understood by the client-side payload predicate, matching
# the conventions used by the other mem0 vector stores (see qdrant.py).
_SUPPORTED_FILTER_OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "nin", "contains", "icontains"}

# create_col(distance=...) -> (index similarity_function, score function used in SELECT)
_DISTANCE_MAPPING = {
    "cosine": ("COSINE", "similarity_cosine"),
    "dot_product": ("DOT_PRODUCT", "similarity_dot_product"),
    "euclidean": ("EUCLIDEAN", "similarity_euclidean"),
}


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a CQL identifier and normalize it to lowercase.

    Unquoted CQL identifiers are folded to lowercase, while the Python driver
    quotes the keyspace in USE statements. Normalizing here keeps DDL and
    connection state consistent for names like 'MyMem0'.
    """
    if not _SAFE_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}': only letters, digits, and underscores are allowed, "
            "must start with a letter or underscore, and be at most 128 characters."
        )
    return name.lower()


def _apply_op(value: Any, op: str, operand: Any) -> bool:
    """Evaluate a single filter operator against a payload value."""
    if op == "eq":
        return value == operand
    if op == "ne":
        return value != operand
    if op in ("gt", "gte", "lt", "lte"):
        if value is None or isinstance(value, bool) or isinstance(operand, bool):
            return False
        try:
            if op == "gt":
                return value > operand
            if op == "gte":
                return value >= operand
            if op == "lt":
                return value < operand
            return value <= operand
        except TypeError:
            return False
    if op == "in":
        return isinstance(operand, (list, tuple, set)) and value in operand
    if op == "nin":
        return isinstance(operand, (list, tuple, set)) and value not in operand
    if op == "contains":
        if isinstance(value, str) and isinstance(operand, str):
            return operand in value
        if isinstance(value, (list, tuple, set)):
            return operand in value
        return False
    if op == "icontains":
        if isinstance(value, str) and isinstance(operand, str):
            return operand.lower() in value.lower()
        return False
    raise ValueError(f"Unsupported filter operator '{op}'. Supported operators: {sorted(_SUPPORTED_FILTER_OPS)}")


def _matches_filters(payload: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    """Evaluate mem0's filter convention against a decoded payload dict.

    Bare values mean equality; dict values use operator syntax
    ({"eq": ...}, {"gte": ...}, ...); AND/OR/NOT combine condition dicts.
    """
    for key, condition in filters.items():
        if key == "AND":
            if not all(_matches_filters(payload, sub) for sub in condition):
                return False
        elif key == "OR":
            if not any(_matches_filters(payload, sub) for sub in condition):
                return False
        elif key == "NOT":
            if any(_matches_filters(payload, sub) for sub in condition):
                return False
        elif isinstance(condition, dict):
            if not all(_apply_op(payload.get(key), op, operand) for op, operand in condition.items()):
                return False
        else:
            if payload.get(key) != condition:
                return False
    return True


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


class ScyllaDB(VectorStoreBase):
    """ScyllaDB vector store backed by ScyllaDB's native vector index.

    Vector search (ANN) is a ScyllaDB Cloud feature (GA since January 2026);
    it is not available in ScyllaDB Open Source or self-managed deployments.
    Filtering columns in the vector index require ScyllaDB Cloud 2026.2 or
    later.
    """

    def __init__(
        self,
        contact_points: List[str],
        port: int = 9042,
        username: Optional[str] = None,
        password: Optional[str] = None,
        keyspace: str = "mem0",
        collection_name: str = "memories",
        embedding_model_dims: int = 1536,
        distance: str = "cosine",
        datacenter: Optional[str] = None,
        use_ssl: bool = False,
        ssl_cert_path: Optional[str] = None,
        replication_strategy: str = "NetworkTopologyStrategy",
        replication_factor: int = 3,
    ):
        """
        Initialize the ScyllaDB vector store.

        Args:
            contact_points: List of contact point addresses
                (e.g., ['node-0.aws-us-east-1.x.clusters.scylla.cloud'])
            port: ScyllaDB CQL port (default: 9042)
            username: Database username (optional)
            password: Database password (optional)
            keyspace: Keyspace name (default: "mem0")
            collection_name: Table name (default: "memories")
            embedding_model_dims: Dimension of the embedding vector (default: 1536)
            distance: Distance metric for the vector index: "cosine" (default),
                "dot_product", or "euclidean"
            datacenter: Local datacenter name for DC-aware routing
                (recommended for ScyllaDB Cloud)
            use_ssl: Enable SSL/TLS (required by ScyllaDB Cloud)
            ssl_cert_path: Path to a CA certificate file for SSL verification.
                Pass None to use the system's default CA bundle.
            replication_strategy: Keyspace replication strategy
                (default: "NetworkTopologyStrategy")
            replication_factor: Keyspace replication factor (default: 3)
        """
        if distance not in _DISTANCE_MAPPING:
            raise ValueError(f"Unsupported distance metric '{distance}'. Supported: {sorted(_DISTANCE_MAPPING)}")
        self.contact_points = contact_points
        self.port = port
        self.username = username
        self.password = password
        self.keyspace = _validate_identifier(keyspace, "keyspace")
        self.collection_name = _validate_identifier(collection_name, "collection_name")
        self.embedding_model_dims = embedding_model_dims
        self.distance = distance
        self._index_similarity, self._score_function = _DISTANCE_MAPPING[distance]
        self.datacenter = datacenter
        self.use_ssl = use_ssl
        self.ssl_cert_path = ssl_cert_path
        self.replication_strategy = replication_strategy
        self.replication_factor = replication_factor

        self.cluster = None
        self.session = None
        self._setup_connection()
        self._create_keyspace()
        self.create_col(name=self.collection_name, vector_size=self.embedding_model_dims)

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
                f"WITH REPLICATION = {{'class': '{self.replication_strategy}', "
                f"'replication_factor': {self.replication_factor}}}"
            )
            self.session.set_keyspace(self.keyspace)
            logger.info(f"Keyspace '{self.keyspace}' is ready")
        except Exception as e:
            logger.error(f"Failed to create keyspace: {e}")
            raise

    def _wait_for_index_ready(self, table_name: str, dims: int):
        """Block until the vector index on *table_name* can serve ANN queries.

        The index builds asynchronously after CREATE CUSTOM INDEX returns, so
        querying it immediately can fail transiently. Polling a cheap ANN
        query here means callers of insert()/search() never have to handle
        that transient state themselves.
        """
        probe = self.session.prepare(f"SELECT id FROM {self.keyspace}.{table_name} ORDER BY vector ANN OF ? LIMIT 1")
        probe_vector = [0.0] * dims
        deadline = time.monotonic() + _INDEX_READY_TIMEOUT_SECONDS
        while True:
            try:
                self.session.execute(probe, (probe_vector,))
                return
            except Exception as e:
                if not _INDEX_BUILDING_RE.search(str(e)) or time.monotonic() >= deadline:
                    raise
                time.sleep(_INDEX_READY_POLL_INTERVAL_SECONDS)

    def create_col(self, name: str = None, vector_size: int = None, distance: str = None):
        """
        Create a new collection (table + vector index) in ScyllaDB.

        The vector index carries user_id/agent_id/run_id as filtering columns
        so scoped searches can be pushed down to the database.

        Args:
            name: Collection name (uses self.collection_name if not provided)
            vector_size: Vector dimension (uses self.embedding_model_dims if not provided)
            distance: Distance metric for the index (uses self.distance if not provided)
        """
        table_name = _validate_identifier(name, "table_name") if name else self.collection_name
        dims = vector_size or self.embedding_model_dims
        metric = distance or self.distance
        if metric not in _DISTANCE_MAPPING:
            raise ValueError(f"Unsupported distance metric '{metric}'. Supported: {sorted(_DISTANCE_MAPPING)}")
        index_similarity, _ = _DISTANCE_MAPPING[metric]

        try:
            # ScyllaDB requires a fixed-width VECTOR<FLOAT, N> type for ANN search.
            self.session.execute(
                f"CREATE TABLE IF NOT EXISTS {self.keyspace}.{table_name} ("
                f"    id text PRIMARY KEY,"
                f"    vector VECTOR<FLOAT, {dims}>,"
                f"    payload text,"
                f"    user_id text,"
                f"    agent_id text,"
                f"    run_id text"
                f")"
            )
            # user_id/agent_id/run_id are declared as filtering columns
            # (requires ScyllaDB Cloud 2026.2+) so equality predicates on them
            # can be evaluated inside the ANN query path.
            self.session.execute(
                f"CREATE CUSTOM INDEX IF NOT EXISTS ON "
                f"{self.keyspace}.{table_name} (vector, user_id, agent_id, run_id) "
                f"USING 'vector_index' "
                f"WITH OPTIONS = {{'similarity_function': '{index_similarity}'}}"
            )
            self._wait_for_index_ready(table_name, dims)
            logger.info(f"Collection '{table_name}' (dimension {dims}) is ready")
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
        if not (len(vectors) == len(payloads) == len(ids)):
            raise ValueError(
                "vectors, payloads, and ids must have matching lengths; got "
                f"{len(vectors)}, {len(payloads)}, and {len(ids)}"
            )

        try:
            prepared = self.session.prepare(
                f"INSERT INTO {self.keyspace}.{self.collection_name} "
                f"(id, vector, payload, user_id, agent_id, run_id) "
                f"VALUES (?, ?, ?, ?, ?, ?)"
            )
            for vec_id, vector, payload in zip(ids, vectors, payloads):
                self.session.execute(
                    prepared,
                    (
                        vec_id,
                        vector,
                        json.dumps(payload),
                        payload.get("user_id"),
                        payload.get("agent_id"),
                        payload.get("run_id"),
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to insert vectors: {e}")
            raise

    def _split_filters(self, filters: Optional[Dict]) -> Tuple[Dict[str, str], Optional[Dict[str, Any]]]:
        """Split filters into server-side scope predicates and residual ones.

        Equality filters on user_id/agent_id/run_id (bare value or {"eq": ...})
        are pushed down to the ANN query's WHERE clause; everything else is
        evaluated client-side over the scoped result set.
        """
        scope: Dict[str, str] = {}
        residual: Dict[str, Any] = {}
        for key, condition in (filters or {}).items():
            if key in _SCOPE_FIELDS:
                if isinstance(condition, str):
                    scope[key] = condition
                    continue
                if isinstance(condition, dict) and set(condition) == {"eq"} and isinstance(condition["eq"], str):
                    scope[key] = condition["eq"]
                    continue
            residual[key] = condition
        return scope, (residual or None)

    def search(
        self,
        query: str,
        vectors: List[float],
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """
        Search for the most similar vectors using ScyllaDB's native ANN index.

        Equality filters on user_id/agent_id/run_id are pushed into the CQL
        WHERE clause (scoped retrieval). Any remaining filters are applied
        client-side over a progressively widened ANN window, so matches are
        never truncated away by a fixed global candidate limit.

        Scores are similarities in [0, 1] where higher means more similar,
        per the VectorStoreBase contract.

        Args:
            query: Query string (not used directly; the embedding vector is used)
            vectors: Query embedding vector
            top_k: Maximum number of results to return
            filters: Optional filters against scope columns or payload fields

        Returns:
            List[OutputData]: Results ordered by descending similarity
        """
        try:
            scope, residual = self._split_filters(filters)

            cql = (
                f"SELECT id, {self._score_function}(vector, ?) AS score, payload "
                f"FROM {self.keyspace}.{self.collection_name}"
            )
            params: List[Any] = [vectors]
            if scope:
                cql += " WHERE " + " AND ".join(f"{field} = ?" for field in scope)
                params.extend(scope.values())
            cql += " ORDER BY vector ANN OF ? LIMIT ?"
            params.append(vectors)
            if scope:
                cql += " ALLOW FILTERING"
            prepared = self.session.prepare(cql)

            limit = top_k
            results: List[OutputData] = []
            while True:
                rows = list(self.session.execute(prepared, tuple(params + [limit])))
                for row in rows:
                    payload = json.loads(row.payload) if row.payload else {}
                    if residual and not _matches_filters(payload, residual):
                        continue
                    results.append(
                        OutputData(
                            id=row.id,
                            # similarity_*() already returns higher-is-better in
                            # [0, 1]; return it unchanged per the base contract.
                            score=float(row.score) if row.score is not None else None,
                            payload=payload,
                        )
                    )
                    if len(results) == top_k:
                        break

                if (
                    not residual
                    or len(results) == top_k
                    or len(rows) < limit  # ANN window exhausted: no more candidates
                    or limit >= _MAX_SEARCH_WINDOW
                ):
                    break
                limit = min(limit * 4, _MAX_SEARCH_WINDOW)

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
            prepared = self.session.prepare(f"DELETE FROM {self.keyspace}.{self.collection_name} WHERE id = ?")
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
        Update a vector's embedding and/or payload in a single CQL statement.

        The payload is serialized before anything is written, and all supplied
        columns are updated atomically, so a failure cannot leave the embedding
        inconsistent with the stored payload. Scope columns are kept in sync
        with the new payload.

        Args:
            vector_id: ID of the record to update
            vector: New embedding vector (skipped if None)
            payload: New payload dict (skipped if None)
        """
        if vector is None and payload is None:
            return

        try:
            assignments: List[str] = []
            params: List[Any] = []
            if vector is not None:
                assignments.append("vector = ?")
                params.append(vector)
            if payload is not None:
                serialized = json.dumps(payload)
                assignments.append("payload = ?")
                params.append(serialized)
                for field in _SCOPE_FIELDS:
                    assignments.append(f"{field} = ?")
                    params.append(payload.get(field))

            cql = f"UPDATE {self.keyspace}.{self.collection_name} SET {', '.join(assignments)} WHERE id = ?"
            prepared = self.session.prepare(cql)
            self.session.execute(prepared, tuple(params + [vector_id]))
            logger.info(f"Updated vector '{vector_id}'")
        except Exception as e:
            logger.error(f"Failed to update vector: {e}")
            raise

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a single vector by ID.

        Database errors are re-raised: only a genuinely missing record returns
        None, so callers can distinguish "not found" from an outage.

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
        except Exception as e:
            logger.error(f"Failed to get vector: {e}")
            raise

        if not row:
            return None
        return OutputData(
            id=row.id,
            score=None,
            payload=json.loads(row.payload) if row.payload else {},
        )

    def list_cols(self) -> List[str]:
        """List all table names in the current keyspace."""
        try:
            prepared = self.session.prepare("SELECT table_name FROM system_schema.tables WHERE keyspace_name = ?")
            rows = self.session.execute(prepared, (self.keyspace,))
            return [row.table_name for row in rows]
        except Exception as e:
            logger.error(f"Failed to list collections: {e}")
            return []

    def delete_col(self):
        """Drop the current collection (table)."""
        try:
            self.session.execute(f"DROP TABLE IF EXISTS {self.keyspace}.{self.collection_name}")
            logger.info(f"Deleted collection '{self.collection_name}'")
        except Exception as e:
            logger.error(f"Failed to delete collection: {e}")
            raise

    def col_info(self) -> Dict[str, Any]:
        """Return basic metadata about the current collection."""
        try:
            row = self.session.execute(f"SELECT COUNT(*) AS count FROM {self.keyspace}.{self.collection_name}").one()
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
        Retrieve up to *top_k* records, optionally filtered.

        Equality filters on user_id/agent_id/run_id are pushed into the WHERE
        clause; all filters are also verified client-side. Rows are consumed
        through the driver's automatic paging and the scan stops as soon as
        *top_k* matches are collected, so matching records are never cut off
        by a fixed LIMIT applied before filtering (this is what makes
        Memory.delete_all() reliable for scoped deletes).

        Args:
            filters: Optional filters against scope columns or payload fields
            top_k: Maximum number of records to return

        Returns:
            A list containing a single inner list of OutputData objects
        """
        try:
            scope, _ = self._split_filters(filters)
            cql = f"SELECT id, payload FROM {self.keyspace}.{self.collection_name}"
            params: List[Any] = []
            if scope:
                cql += " WHERE " + " AND ".join(f"{field} = ?" for field in scope)
                params.extend(scope.values())
                cql += " ALLOW FILTERING"
            prepared = self.session.prepare(cql)

            results: List[OutputData] = []
            for row in self.session.execute(prepared, tuple(params)):
                payload = json.loads(row.payload) if row.payload else {}
                if filters and not _matches_filters(payload, filters):
                    continue
                results.append(OutputData(id=row.id, score=None, payload=payload))
                if len(results) == top_k:
                    break
            return [results]
        except Exception as e:
            # Re-raise so callers (e.g. Memory.delete_all) cannot mistake an
            # outage for "no records" and report success.
            logger.error(f"Failed to list vectors: {e}")
            raise

    def reset(self):
        """Reset the collection by dropping and recreating the table and index.

        TRUNCATE is intentionally avoided: it does not propagate to the CDC
        log, so the vector index would retain stale vectors. Dropping and
        recreating the table (and its index) is the only correct way to fully
        clear vector index state.
        """
        try:
            logger.warning(f"Resetting collection '{self.collection_name}'...")
            self.session.execute(f"DROP TABLE IF EXISTS {self.keyspace}.{self.collection_name}")
            self.create_col(name=self.collection_name, vector_size=self.embedding_model_dims)
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
