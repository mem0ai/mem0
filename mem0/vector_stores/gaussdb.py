import hashlib
import json
import logging
import math
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel

try:
    from psycopg2.extensions import TRANSACTION_STATUS_UNKNOWN, make_dsn
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    TRANSACTION_STATUS_UNKNOWN = None
    make_dsn = None
    ThreadedConnectionPool = None

from mem0.configs.vector_stores.gaussdb import (
    _IDENTIFIER_RE,
    _MEMORY_SETTING_RE,
    _first_env,
    _validate_positive_int,
    validate_gaussdb_static_options,
)
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_FILTER_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_ISO_8601_TIMESTAMPTZ_PATTERN = (
    r"^[[:digit:]]{4}-[[:digit:]]{2}-[[:digit:]]{2}"
    r"([T ][[:digit:]]{2}:[[:digit:]]{2}"
    r"(:[[:digit:]]{2}([.][[:digit:]]+)?)?"
    r"(Z|[+-][[:digit:]]{2}(:?[[:digit:]]{2})?)?)?$"
)
_ISO_8601_DATETIME_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"([T ]\d{2}:\d{2}"
    r"(:\d{2}([.]\d+)?)?"
    r"(Z|[+-]\d{2}(:?\d{2})?)?)?$"
)
_RETRYABLE_ERROR_FRAGMENTS = (
    "connection",
    "timeout",
    "deadlock",
    "lock wait",
    "could not serialize",
    "serialization failure",
    "server closed",
    "terminating connection",
)
_CONNECTION_ERROR_FRAGMENTS = (
    "connection already closed",
    "connection not open",
    "connection reset",
    "connection refused",
    "eof detected",
    "server closed",
    "ssl connection has been closed",
    "terminating connection",
)
_BM25_UNAVAILABLE_ERROR_FRAGMENTS = (
    "no bm25 index is used",
    "gs_bm25_distance_text is called",
)
_DEFAULT_VECTOR_INDEX_MAINTENANCE_WORK_MEM = "256MB"
_HIGH_DIM_VECTOR_INDEX_MAINTENANCE_WORK_MEM = "2GB"
_SUPPORTED_FILTER_OPERATORS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "nin",
    "contains",
    "icontains",
}
_RANGE_FILTER_OPERATORS = {"gt", "gte", "lt", "lte"}


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


@dataclass
class _FilterBuildResult:
    expression: str
    params: List[Any]


@dataclass
class CapabilityReport:
    baseline: str
    vector_enabled: bool = False
    floatvector: bool = False
    vector_index: bool = False
    bm25: bool = False
    jsonb: bool = False
    uuid: bool = False
    expression_index: bool = False
    payload_storage_mode: str = "jsonb"
    filter_storage_mode: str = "json_expression"
    metadata_column_mode: str = "jsonb"
    deployment_mode: str = "centralized"
    distribution_mode: str = "none"


class GaussDB(VectorStoreBase):
    """
    GaussDB vector store provider for mem0.

    The implementation uses the psycopg2 API with a build that is compatible
    with the target GaussDB environment. It avoids psycopg3-specific APIs
    because GaussDB's Python examples use psycopg2.
    """

    _redundant_scope_columns = ("user_id", "agent_id", "run_id")

    def __init__(
        self,
        database: Optional[str] = None,
        collection_name: str = "mem0",
        embedding_model_dims: int = 1536,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        connection_string: Optional[str] = None,
        minconn: int = 1,
        maxconn: int = 5,
        insert_batch_size: int = 2000,
        vector_index_maintenance_work_mem: Optional[str] = None,
        sslmode: Optional[str] = None,
        sslrootcert: Optional[str] = None,
        schema_name: Optional[str] = None,
        deployment_mode: str = "centralized",
        vector_index_type: str = "gsdiskann",
        vector_metric: str = "cosine",
        auto_create: bool = True,
    ):
        connection_string = connection_string or _first_env("GAUSSDB_CONNECTION_STRING", "GAUSSDB_DSN", "GAUSSDB_URL")
        database = database or _first_env("GAUSSDB_DATABASE", "GAUSSDB_DBNAME") or "postgres"
        user = user or _first_env("GAUSSDB_USER")
        password = password or _first_env("GAUSSDB_PASSWORD")
        host = host or _first_env("GAUSSDB_HOST")
        port = port or _first_env("GAUSSDB_PORT")
        sslmode = sslmode or _first_env("GAUSSDB_SSLMODE")
        sslrootcert = sslrootcert or _first_env("GAUSSDB_SSLROOTCERT")
        schema_name = schema_name or _first_env("GAUSSDB_SCHEMA_NAME", "GAUSSDB_SCHEMA") or "public"
        self.database = database
        self.collection_name = self._validate_identifier(collection_name, "collection_name")
        self.embedding_model_dims = embedding_model_dims
        self.user = user
        self.password = password
        self.host = host
        self.port = int(port) if port is not None else None
        self.connection_string = connection_string
        self.minconn = minconn
        self.maxconn = maxconn
        self.insert_batch_size = insert_batch_size
        self.vector_index_maintenance_work_mem = vector_index_maintenance_work_mem
        self.sslmode = sslmode
        self.sslrootcert = sslrootcert
        self.deployment_mode = str(deployment_mode).lower()
        self.vector_index_type = vector_index_type.lower()
        self.vector_metric = vector_metric.lower()
        validate_gaussdb_static_options(
            embedding_model_dims=self.embedding_model_dims,
            insert_batch_size=self.insert_batch_size,
            minconn=self.minconn,
            maxconn=self.maxconn,
            schema_name=schema_name,
            deployment_mode=self.deployment_mode,
            vector_index_type=self.vector_index_type,
            vector_metric=self.vector_metric,
        )

        self.distribution_mode = "hash" if self.deployment_mode == "distributed" else "none"

        self.schema_name = self._validate_identifier(schema_name, "schema_name")
        self.table_storage = "ustore"
        self.id_column_type = "uuid"
        self.gsdiskann_subgraph_count = 1
        self.bm25_enabled = self.deployment_mode != "distributed"
        self.bm25_ranking_metric = 0
        self.bm25_ncandidates = 128
        self.payload_storage_mode = "jsonb"
        self.filter_storage_mode = "json_expression"
        self.metadata_column_mode = "jsonb"
        self.allowed_filter_keys = None
        self.slow_query_ms = 1000
        self.retry_attempts = 2
        self.retry_backoff_seconds = 0.1
        self.gaussdb_version_baseline = "506"

        self.capabilities = CapabilityReport(
            baseline=self.gaussdb_version_baseline,
            vector_enabled=True,
            floatvector=True,
            vector_index=True,
            bm25=self.bm25_enabled,
            jsonb=True,
            uuid=self.id_column_type == "uuid",
            expression_index=True,
            payload_storage_mode=self.payload_storage_mode,
            filter_storage_mode=self.filter_storage_mode,
            metadata_column_mode=self.metadata_column_mode,
            deployment_mode=self.deployment_mode,
            distribution_mode=self.distribution_mode,
        )
        self._schema_prefix = f'"{self.schema_name}".'
        self.table_name = f"{self._schema_prefix}{self._quote_identifier(self.collection_name)}"

        self.connection_pool = self._create_connection_pool()

        if auto_create:
            collections = self.list_cols()
            if self.collection_name not in collections:
                self.create_col()
            elif self.bm25_enabled:
                # Collection exists; verify a BM25 index is actually usable
                # rather than assuming bm25_enabled from deployment_mode alone.
                with self._get_cursor() as cur:
                    cur.execute(
                        """
                        SELECT 1
                        FROM pg_index pi
                        JOIN pg_class idx_cls ON pi.indexrelid = idx_cls.oid
                        JOIN pg_am am ON idx_cls.relam = am.oid
                        JOIN pg_class tbl_cls ON pi.indrelid = tbl_cls.oid
                        JOIN pg_namespace ns ON tbl_cls.relnamespace = ns.oid
                        WHERE ns.nspname = %s
                          AND tbl_cls.relname = %s
                          AND am.amname = 'bm25'
                          AND pi.indisvalid IS TRUE
                          AND pi.indisusable IS TRUE
                        """,
                        (self.schema_name, self.collection_name),
                    )
                    self.bm25_enabled = cur.fetchone() is not None
                    self.capabilities.bm25 = self.bm25_enabled

    @staticmethod
    def _validate_choice(value: str, field_name: str, choices: set[str]) -> str:
        if value not in choices:
            raise ValueError(f"{field_name} must be one of {sorted(choices)}")
        return value

    @classmethod
    def _validate_identifier(cls, value: str, field_name: str = "identifier") -> str:
        if not isinstance(value, str) or not _IDENTIFIER_RE.match(value):
            raise ValueError(
                f"Unsafe {field_name}: {value!r}. Use letters, numbers, and underscores; start with a letter or underscore."
            )
        return value

    @classmethod
    def _quote_identifier(cls, value: str) -> str:
        return f'"{cls._validate_identifier(value)}"'

    @classmethod
    def _index_name(cls, collection_name: str, suffix: str) -> str:
        raw = f"{collection_name}_{suffix}"
        if len(raw) <= 63 and _IDENTIFIER_RE.match(raw):
            return raw
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        prefix = collection_name[: max(1, 63 - len(suffix) - len(digest) - 2)]
        return cls._validate_identifier(f"{prefix}_{digest}_{suffix}")

    def _validate_filter_key(self, key: str) -> str:
        if not isinstance(key, str) or not _FILTER_KEY_RE.match(key):
            raise ValueError(f"Unsafe filter key: {key!r}")
        if self.allowed_filter_keys is not None and key not in self.allowed_filter_keys:
            raise ValueError(f"Unsupported filter key: {key!r}")
        return key

    @staticmethod
    def _escape_like(value: str) -> str:
        """Escape LIKE metacharacters so they match literally."""
        return value.replace("!", "!!").replace("%", "!%").replace("_", "!_")

    @contextmanager
    def _savepoint(self, cur, name: str):
        cur.execute(f"SAVEPOINT {name}")
        try:
            yield
            cur.execute(f"RELEASE SAVEPOINT {name}")
        except Exception:
            try:
                cur.execute(f"ROLLBACK TO SAVEPOINT {name}")
                cur.execute(f"RELEASE SAVEPOINT {name}")
            except Exception:
                logger.debug("Failed to roll back savepoint %s", name, exc_info=True)
            raise

    def _create_connection_pool(self):
        if ThreadedConnectionPool is None or make_dsn is None:
            raise ImportError(
                "GaussDB vector store requires psycopg2. "
                "Install it with: pip install psycopg2 "
                "(or pip install psycopg2-binary for a pre-compiled wheel). "
                "If your GaussDB environment requires a vendor-specific build, "
                "use the psycopg2 wheel from the GaussDB documentation instead."
            )

        dsn = self._build_dsn()
        logger.info("Creating GaussDB connection pool for %s", self._sanitize_dsn(dsn))
        return ThreadedConnectionPool(minconn=self.minconn, maxconn=self.maxconn, dsn=dsn)

    def _build_dsn(self) -> str:
        if self.connection_string:
            overrides = {"client_encoding": "UTF8"}
            if self.sslmode:
                overrides["sslmode"] = self.sslmode
            if self.sslrootcert:
                overrides["sslrootcert"] = self.sslrootcert
            return make_dsn(self.connection_string, **overrides)

        missing = [
            name
            for name, value in {
                "user": self.user,
                "password": self.password,
                "host": self.host,
                "port": self.port,
            }.items()
            if not value
        ]
        if missing:
            raise ValueError(
                f"GaussDB connection requires connection_string or individual fields. Missing: {', '.join(missing)}"
            )

        parts = {
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": str(self.port),
            "client_encoding": "UTF8",
        }
        if self.sslmode:
            parts["sslmode"] = self.sslmode
        if self.sslrootcert:
            parts["sslrootcert"] = self.sslrootcert
        return " ".join(f"{key}={self._quote_dsn_value(value)}" for key, value in parts.items() if value is not None)

    @staticmethod
    def _quote_dsn_value(value: str) -> str:
        text = str(value)
        if text == "":
            return "''"
        if re.search(r"\s|'|\\", text):
            return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"
        return text

    @staticmethod
    def _sanitize_dsn(dsn: str) -> str:
        sanitized = re.sub(r"(password=)(('[^']*')|(\S+))", r"\1<redacted>", dsn)
        sanitized = re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1<redacted>\3", sanitized)
        return sanitized

    @contextmanager
    def _get_cursor(self, commit: bool = False, log_errors: bool = True):
        conn = self.connection_pool.getconn()
        cur = None
        discard_conn = False
        try:
            cur = conn.cursor()
            try:
                yield cur
                if commit:
                    conn.commit()
                else:
                    conn.rollback()
            except Exception as exc:
                discard_conn = self._should_discard_connection(conn, exc)
                try:
                    conn.rollback()
                except Exception:
                    discard_conn = True
                    logger.debug("Failed to roll back GaussDB transaction; discarding connection", exc_info=True)
                if log_errors:
                    logger.exception("GaussDB operation failed; transaction rollback attempted")
                raise
            finally:
                if cur is not None:
                    try:
                        cur.close()
                    except Exception:
                        discard_conn = True
                        logger.debug("Failed to close GaussDB cursor; discarding connection", exc_info=True)
        finally:
            if discard_conn:
                self.connection_pool.putconn(conn, close=True)
            else:
                self.connection_pool.putconn(conn)

    @classmethod
    def _should_discard_connection(cls, conn, exc: Optional[Exception] = None) -> bool:
        closed = getattr(conn, "closed", 0)
        if isinstance(closed, (bool, int)) and bool(closed):
            return True

        info = getattr(conn, "info", None)
        transaction_status = getattr(info, "transaction_status", None)
        if TRANSACTION_STATUS_UNKNOWN is not None and transaction_status == TRANSACTION_STATUS_UNKNOWN:
            return True

        if exc is not None:
            message = str(exc).lower()
            return any(fragment in message for fragment in _CONNECTION_ERROR_FRAGMENTS)

        return False

    def _run_with_retry(self, operation: str, func):
        attempts = max(1, self.retry_attempts + 1)
        delay = self.retry_backoff_seconds
        last_exc = None
        for attempt in range(attempts):
            start = time.perf_counter()
            try:
                result = func()
                self._record_latency(operation, start, "success")
                return result
            except Exception as exc:
                self._record_latency(operation, start, "error")
                last_exc = exc
                if attempt >= attempts - 1 or not self._is_retryable(exc):
                    raise
                logger.warning("Retrying GaussDB operation %s after transient error: %s", operation, exc)
                time.sleep(delay)
                delay *= 2
        raise last_exc

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(fragment in message for fragment in _RETRYABLE_ERROR_FRAGMENTS)

    @staticmethod
    def _is_bm25_unavailable_error(exc: Exception) -> bool:
        message = str(exc).lower()
        if any(fragment in message for fragment in _BM25_UNAVAILABLE_ERROR_FRAGMENTS):
            return True
        return "bm25" in message and (
            "not currently supported" in message
            or ("operator does not exist" in message and "###" in message)
            or ("function does not exist" in message)
        )

    def _record_latency(self, operation: str, start: float, outcome: str):
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= self.slow_query_ms:
            logger.debug("Slow GaussDB operation op=%s outcome=%s latency_ms=%.2f", operation, outcome, elapsed_ms)

    @staticmethod
    def _chunked(sequence: Sequence[Any], size: int) -> Iterable[Sequence[Any]]:
        for index in range(0, len(sequence), size):
            yield sequence[index : index + size]

    @property
    def _vector_operator(self) -> str:
        # In current GaussDB vector semantics, <+> maps to cosine distance.
        # Do not assume pgvector operator meanings here.
        return "<+>" if self.vector_metric == "cosine" else "<->"

    @property
    def _vector_index_metric(self) -> str:
        return "COSINE" if self.vector_metric == "cosine" else "L2"

    def _id_column_sql(self) -> str:
        return "UUID" if self.id_column_type == "uuid" else "VARCHAR(36)"

    def _payload_column_sql(self) -> str:
        return "JSONB"

    def _create_table_suffix_sql(self, distribution_key: str) -> str:
        suffix = f"WITH (storage_type={self.table_storage})"
        distribution_clause = self._distribution_clause_sql(distribution_key)
        if distribution_clause:
            suffix = f"{suffix}\n                    {distribution_clause}"
        return suffix

    def _distribution_clause_sql(self, distribution_key: str) -> str:
        if self.distribution_mode == "none":
            return ""
        if self.distribution_mode == "hash":
            return f"DISTRIBUTE BY HASH ({self._quote_identifier(distribution_key)})"
        raise ValueError(f"Unsupported distribution_mode: {self.distribution_mode}")

    def _payload_value(self, payload: dict):
        # Always serialize as a plain JSON string. Avoid psycopg2's Json adapter
        # and let the SQL cast (::JSONB) handle the type conversion on the
        # server side. Keep the JSON text ASCII-escaped by default so payload
        # transport stays conservative even when metadata contains non-ASCII
        # text; JSONB parsing restores the original string values.
        return self._dump_json(payload, "GaussDB payload")

    @staticmethod
    def _dump_json(value: Any, context: str, **kwargs) -> str:
        try:
            return json.dumps(value, allow_nan=False, **kwargs)
        except ValueError as exc:
            raise ValueError(f"{context} must be valid JSON; NaN and Infinity are not supported") from exc

    @staticmethod
    def _decode_payload(payload: Any) -> dict:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            return json.loads(payload)
        if isinstance(payload, bytes):
            return json.loads(payload.decode("utf-8"))
        return dict(payload)

    @staticmethod
    def _vector_literal(vector: Sequence[float]) -> str:
        # Client-side FLOATVECTOR literal. Avoids psycopg2's Latin-1 encoding issue
        # (see _payload_value rationale). The server-side ::FLOATVECTOR cast parses
        # this string format. GaussDB requires dimensions > 0.
        if not vector:
            raise ValueError("Vector must have at least one dimension; got empty vector")
        parts = []
        for index, value in enumerate(vector):
            numeric = float(value)
            if not math.isfinite(numeric):
                raise ValueError(f"Vector values must be finite numbers; got {value!r} at index {index}")
            parts.append(str(numeric))
        return "[" + ",".join(parts) + "]"

    def _schema_exists(self, cur) -> bool:
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = %s",
            (self.schema_name,),
        )
        return bool(cur.fetchone()[0])

    def _ensure_schema(self, cur) -> None:
        """Create the target schema, tolerating concurrent creation races."""
        try:
            with self._savepoint(cur, "mem0_create_schema"):
                cur.execute(f'CREATE SCHEMA "{self.schema_name}"')
        except Exception:
            if not self._schema_exists(cur):
                raise

    def create_col(self, name: Optional[str] = None, vector_size: int = None, distance: str = None) -> None:
        """Create the configured GaussDB collection and its indexes.

        Args:
            name: Optional collection name override. GaussDB instances are bound to
                ``self.collection_name``, so alternate names are rejected.
            vector_size: Optional vector dimension compatibility parameter.
                If provided, it must match ``self.embedding_model_dims``.
            distance: Optional vector distance metric override (``cosine`` or ``l2``).

        Returns:
            None.
        """
        if name is not None:
            validated_name = self._validate_identifier(name, "collection_name")
            if validated_name != self.collection_name:
                raise ValueError(
                    f"GaussDB create_col only supports the configured collection_name {self.collection_name!r}; "
                    f"got {validated_name!r}"
                )
        table = self.table_name
        dims = self.embedding_model_dims
        if vector_size is not None:
            requested_dims = _validate_positive_int(vector_size, "vector_size")
            if requested_dims != self.embedding_model_dims:
                raise ValueError(
                    "GaussDB create_col vector_size must match embedding_model_dims "
                    f"({self.embedding_model_dims}); got {requested_dims}. "
                    "Set embedding_model_dims when constructing GaussDB instead."
                )
        effective_metric = self.vector_metric
        if distance:
            effective_metric = self._validate_choice(distance.lower(), "distance", {"cosine", "l2"})
        validate_gaussdb_static_options(
            embedding_model_dims=dims,
            insert_batch_size=self.insert_batch_size,
            minconn=self.minconn,
            maxconn=self.maxconn,
            schema_name=self.schema_name,
            deployment_mode=self.deployment_mode,
            vector_index_type=self.vector_index_type,
            vector_metric=effective_metric,
        )
        if distance:
            self.vector_metric = effective_metric

        def op():
            with self._get_cursor(commit=True) as cur:
                self._ensure_schema(cur)
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id {self._id_column_sql()} PRIMARY KEY,
                        vector FLOATVECTOR({dims}),
                        payload {self._payload_column_sql()},
                        text_lemmatized TEXT,
                        user_id TEXT,
                        agent_id TEXT,
                        run_id TEXT
                    ) {self._create_table_suffix_sql("id")}
                    """
                )
                self._ensure_indexes(cur, table, embedding_dims=dims)

        return self._run_with_retry("create_col", op)

    def _create_vector_index(self, cur, table: str, embedding_dims: Optional[int] = None):
        index_name = self._quote_identifier(self._index_name(self.collection_name, "vector_idx"))
        self._set_vector_index_maintenance_work_mem(cur, embedding_dims=embedding_dims)
        with_clause = self._vector_index_with_clause(embedding_dims=embedding_dims)
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table}
            USING {self.vector_index_type} (vector {self._vector_index_metric})
            {with_clause}
            """
        )

    def _vector_index_with_clause(self, embedding_dims: Optional[int] = None) -> str:
        """Build WITH clause for vector index. High-dim GsDiskANN needs enable_vector_copy=false + subgraph_count>0."""
        dims = self.embedding_model_dims if embedding_dims is None else embedding_dims
        if self.vector_index_type == "gsdiskann" and dims > 1024:
            return f"WITH (enable_vector_copy=false, subgraph_count={self.gsdiskann_subgraph_count})"
        return ""

    def _set_vector_index_maintenance_work_mem(self, cur, embedding_dims: Optional[int] = None):
        dims = self.embedding_model_dims if embedding_dims is None else embedding_dims
        target_mem = self.vector_index_maintenance_work_mem
        if target_mem is None:
            target_mem = (
                _HIGH_DIM_VECTOR_INDEX_MAINTENANCE_WORK_MEM
                if dims > 1024
                else _DEFAULT_VECTOR_INDEX_MAINTENANCE_WORK_MEM
            )
        if not target_mem:
            return
        target_bytes = self._parse_memory_setting_bytes(target_mem)
        if target_bytes is None:
            return
        cur.execute("SHOW maintenance_work_mem")
        row = cur.fetchone()
        current_value = row[0] if row else None
        current_bytes = self._parse_memory_setting_bytes(current_value)
        if current_bytes is None or current_bytes < target_bytes:
            cur.execute("SET LOCAL maintenance_work_mem = %s", (target_mem,))

    @staticmethod
    def _parse_memory_setting_bytes(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return int(value)
        match = _MEMORY_SETTING_RE.match(str(value))
        if not match:
            return None
        amount = float(match.group(1))
        unit = match.group(2).lower()
        multipliers = {
            "b": 1,
            "bytes": 1,
            "kb": 1024,
            "kib": 1024,
            "mb": 1024**2,
            "mib": 1024**2,
            "gb": 1024**3,
            "gib": 1024**3,
            "tb": 1024**4,
            "tib": 1024**4,
        }
        multiplier = multipliers.get(unit)
        if multiplier is None:
            return None
        return int(amount * multiplier)

    def _create_bm25_index(self, cur, table: str, index_name: Optional[str] = None):
        index_name = index_name or self._quote_identifier(self._index_name(self.collection_name, "bm25_idx"))
        try:
            with self._savepoint(cur, f"mem0_bm25_{uuid.uuid4().hex[:8]}"):
                cur.execute(
                    f"""
                    CREATE INDEX IF NOT EXISTS {index_name}
                    ON {table}
                    USING bm25 (text_lemmatized)
                    WITH (storage_type='USTORE')
                    """
                )
        except Exception:
            self.bm25_enabled = False
            self.capabilities.bm25 = False
            logger.warning("BM25 index creation failed; keyword_search disabled", exc_info=True)

    def _create_filter_indexes(self, cur, table: str):
        for key in self._redundant_scope_columns:
            safe_key = self._validate_filter_key(key)
            index_name = self._quote_identifier(self._index_name(self.collection_name, f"{safe_key}_idx"))
            try:
                with self._savepoint(cur, f"mem0_filter_idx_{uuid.uuid4().hex[:8]}"):
                    cur.execute(
                        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({self._quote_identifier(safe_key)})"
                    )
            except Exception as exc:
                logger.warning(
                    "Filter index creation failed for key %s; continuing without this index: %s", safe_key, exc
                )

    def _ensure_indexes(self, cur, table: str, embedding_dims: Optional[int] = None):
        self._create_vector_index(cur, table, embedding_dims=embedding_dims)
        if self.bm25_enabled:
            self._create_bm25_index(cur, table)
        self._create_filter_indexes(cur, table)

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> None:
        """
        Insert or upsert vectors and payloads into the collection.

        Args:
            vectors (List[List[float]]): Vectors to insert.
            payloads (List[Dict], optional): Payloads associated with each vector. Defaults to empty payloads.
            ids (List[str], optional): IDs associated with each vector. Defaults to generated UUIDs.

        Returns:
            None
        """
        payloads = [{} for _ in vectors] if payloads is None else payloads
        ids = [str(uuid.uuid4()) for _ in vectors] if ids is None else ids
        if len(vectors) != len(payloads) or len(vectors) != len(ids):
            raise ValueError("vectors, payloads, and ids must have the same length")
        if len(ids) != len(set(ids)):
            raise ValueError("ids must be unique within a single insert() call")

        rows = [
            self._insert_row(vector, payload, vector_id) for vector, payload, vector_id in zip(vectors, payloads, ids)
        ]
        if not rows:
            return None
        columns = ["id", "vector", "payload", "text_lemmatized", *self._redundant_scope_columns]
        update_columns = [column for column in columns if column != "id"]
        update_set_sql = ", ".join(
            f"{self._quote_identifier(column)} = src.{self._quote_identifier(column)}" for column in update_columns
        )
        insert_columns_sql = ", ".join(self._quote_identifier(column) for column in columns)
        insert_values_sql = ", ".join(f"src.{self._quote_identifier(column)}" for column in columns)
        src_columns_sql = ", ".join(self._quote_identifier(column) for column in columns)

        def op():
            with self._get_cursor(commit=True) as cur:
                for chunk_rows in self._chunked(rows, self.insert_batch_size):
                    values_sql = ", ".join([self._incoming_values_sql(columns)] * len(chunk_rows))
                    flat_params = tuple(value for row in chunk_rows for value in row)
                    # MERGE INTO: GaussDB A-mode (Oracle compatible) atomic upsert.
                    # Chunk large batches to avoid oversized VALUES clauses while
                    # preserving all-or-nothing semantics for a single insert() call.
                    cur.execute(
                        f"""
                        MERGE INTO {self.table_name} AS target
                        USING (VALUES {values_sql}) AS src ({src_columns_sql})
                        ON (target.id = src.id)
                        WHEN MATCHED THEN
                            UPDATE SET {update_set_sql}
                        WHEN NOT MATCHED THEN
                            INSERT ({insert_columns_sql})
                            VALUES ({insert_values_sql})
                        """,
                        flat_params,
                    )

        return self._run_with_retry("insert", op)

    def _incoming_values_sql(self, columns: List[str]) -> str:
        casts = {
            "id": self._id_column_sql(),
            "vector": "FLOATVECTOR",
            "payload": self._payload_column_sql(),
            "text_lemmatized": "TEXT",
            "user_id": "TEXT",
            "agent_id": "TEXT",
            "run_id": "TEXT",
        }
        placeholders = [f"%s::{casts[column]}" if column in casts else "%s" for column in columns]
        return "(" + ", ".join(placeholders) + ")"

    def _insert_row(self, vector: Sequence[float], payload: dict, vector_id: str) -> Tuple:
        payload = payload or {}
        text_lemmatized = payload.get("text_lemmatized") or payload.get("data")
        row = [
            vector_id,
            self._vector_literal(vector),
            self._payload_value(payload),
            text_lemmatized,
        ]
        row.extend(payload.get(key) for key in self._redundant_scope_columns)
        return tuple(row)

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[dict] = None
    ) -> List[OutputData]:
        """
        Search for vectors similar to the query vector.

        Args:
            query (str): Query text associated with the search.
            vectors (List[float]): Query vector.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            List[OutputData]: Search results ordered by vector distance.
        """
        where_clause, params = self._build_where_clause(filters)
        vector_literal = self._vector_literal(vectors)

        def op():
            with self._get_cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, vector {self._vector_operator} %s::FLOATVECTOR AS distance, payload
                    FROM {self.table_name}
                    {where_clause}
                    ORDER BY distance ASC, id ASC
                    LIMIT %s
                    """,
                    (vector_literal, *params, top_k),
                )
                rows = cur.fetchall()
            outputs = []
            for row in rows:
                distance = float(row[1])
                if self.vector_metric == "cosine":
                    # GaussDB <+> returns cosine distance [0, 2]. Convert to
                    # mem0's [0, 1] similarity contract (higher is better) so that
                    # downstream scoring (score_and_rank threshold, entity
                    # dedup >= 0.95, reranker) aligns with Qdrant/Weaviate.
                    # See: mem0ai/mem0#4453, weaviate.py `1 - obj.metadata.distance`.
                    score = max(0.0, min(1.0, 1.0 - distance))
                elif self.vector_metric == "l2":
                    # L2 distance [0, +inf). Compress to (0, 1] so higher is
                    # more similar, preserving the raw-distance ordering.
                    score = 1.0 / (1.0 + max(0.0, distance))
                else:
                    score = max(0.0, distance)
                outputs.append(OutputData(id=str(row[0]), score=score, payload=self._decode_payload(row[2])))
            return outputs

        return self._run_with_retry("search", op)

    def keyword_search(self, query: str, top_k: int = 5, filters: Optional[dict] = None):
        """
        Search using GaussDB BM25 keyword ranking when available.

        Args:
            query (str): Query text.
            top_k (int, optional): Number of results to return. Defaults to 5.
            filters (dict, optional): Filters to apply to the search. Defaults to None.

        Returns:
            Optional[List[OutputData]]: Keyword search results, or None when BM25 is unavailable.
        """
        if not self.bm25_enabled:
            return None
        if not query or not query.strip():
            return []

        where_clause, params = self._build_where_clause(filters)
        prefix = " AND " if where_clause else " WHERE "
        bm25_hint = self._bm25_index_hint()

        def op():
            try:
                with self._get_cursor(log_errors=False) as cur:
                    self._apply_bm25_settings(cur)
                    cur.execute(
                        f"""
                        SELECT {bm25_hint} id, text_lemmatized ### %s AS score, payload
                        FROM {self.table_name}
                        {where_clause}
                        {prefix}(text_lemmatized ### %s) > 0
                        ORDER BY score DESC
                        LIMIT %s
                        """,
                        (query, *params, query, top_k),
                    )
                    rows = cur.fetchall()
                return [
                    OutputData(id=str(row[0]), score=float(row[1]), payload=self._decode_payload(row[2]))
                    for row in rows
                ]
            except Exception as exc:
                if self._is_bm25_unavailable_error(exc):
                    logger.debug("GaussDB BM25 keyword search unavailable; falling back", exc_info=True)
                    return None
                raise

        return self._run_with_retry("keyword_search", op)

    def _bm25_index_hint(self) -> str:
        index_name = self._quote_identifier(self._index_name(self.collection_name, "bm25_idx"))
        table_name = self._quote_identifier(self.collection_name)
        return f"/*+ indexscan({table_name} {index_name}) */"

    def _apply_bm25_settings(self, cur):
        # int() coercion guarantees these are numeric, so f-string interpolation
        # is safe against injection. SET LOCAL does not accept %s parameter binding
        # in GaussDB's psycopg2 driver; the value must be embedded in the statement.
        cur.execute(f"SET LOCAL bm25_ranking_metric = {int(self.bm25_ranking_metric)}")
        cur.execute(f"SET LOCAL bm25_ncandidates = {int(self.bm25_ncandidates)}")
        cur.execute("SET LOCAL enable_seqscan = off")

    def search_batch(self, queries: list, vectors_list: list, top_k: int = 1, filters: Optional[dict] = None):
        """
        Run vector search for multiple query vectors.

        Args:
            queries (list): Query texts associated with each vector.
            vectors_list (list): Query vectors.
            top_k (int, optional): Number of results to return per query. Defaults to 1.
            filters (dict, optional): Filters to apply to each search. Defaults to None.

        Returns:
            List[List[OutputData]]: Search results for each query vector.
        """
        if not vectors_list:
            return []
        if len(queries) != len(vectors_list):
            raise ValueError(
                f"search_batch: queries ({len(queries)}) and vectors_list ({len(vectors_list)}) length mismatch"
            )
        return [
            self.search(query, vectors, top_k=top_k, filters=filters) for query, vectors in zip(queries, vectors_list)
        ]

    def delete(self, vector_id: str) -> None:
        """
        Delete a vector by ID.

        Args:
            vector_id (str): ID of the vector to delete.

        Returns:
            None
        """

        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(f"DELETE FROM {self.table_name} WHERE id = %s", (vector_id,))

        return self._run_with_retry("delete", op)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[dict] = None) -> None:
        """
        Update a vector and/or replace its payload.

        Args:
            vector_id (str): ID of the vector to update.
            vector (List[float], optional): Updated vector. Defaults to None.
            payload (dict, optional): Replacement payload. Defaults to None.

        Returns:
            None
        """
        if vector is None and payload is None:
            return None

        set_clauses = []
        params = []
        if vector is not None:
            set_clauses.append("vector = %s::FLOATVECTOR")
            params.append(self._vector_literal(vector))
        if payload is not None:
            text_lemmatized = payload.get("text_lemmatized") or payload.get("data")
            set_clauses.extend([f"payload = %s::{self._payload_column_sql()}", "text_lemmatized = %s"])
            params.extend([self._payload_value(payload), text_lemmatized])
            # Scope columns are set from payload.get(key), which returns None if the
            # key is absent. This is a full-replacement update: scope columns that are
            # not in the payload become NULL. mem0's upper-level code always preserves
            # scope keys from the existing memory when building the update payload, so
            # this does not cause data loss in normal mem0 usage. Direct callers who
            # omit scope keys should be aware that missing keys will NULL the column.
            for key in self._redundant_scope_columns:
                set_clauses.append(f"{self._quote_identifier(key)} = %s")
                params.append(payload.get(key))
        params.append(vector_id)

        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET {", ".join(set_clauses)}
                    WHERE id = %s
                    """,
                    tuple(params),
                )

        return self._run_with_retry("update", op)

    def get(self, vector_id: str) -> Optional[OutputData]:
        """
        Retrieve a vector payload by ID.

        Args:
            vector_id (str): ID of the vector to retrieve.

        Returns:
            Optional[OutputData]: Retrieved vector payload, or None if the ID does not exist.
        """

        def op():
            with self._get_cursor() as cur:
                cur.execute(f"SELECT id, payload FROM {self.table_name} WHERE id = %s", (vector_id,))
                row = cur.fetchone()
            if not row:
                return None
            return OutputData(id=str(row[0]), score=None, payload=self._decode_payload(row[1]))

        return self._run_with_retry("get", op)

    def list_cols(self) -> List[str]:
        """
        List collection tables in the configured schema.

        Args:
            None

        Returns:
            List[str]: Collection table names.
        """

        def op():
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    """,
                    (self.schema_name,),
                )
                rows = cur.fetchall()
            return [row[0] for row in rows]

        return self._run_with_retry("list_cols", op)

    def delete_col(self) -> None:
        """
        Delete the current collection table.

        Args:
            None

        Returns:
            None
        """

        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(f"DROP TABLE IF EXISTS {self.table_name}")

        return self._run_with_retry("delete_col", op)

    def col_info(self) -> Dict[str, Any]:
        """
        Return metadata about the current collection.

        Args:
            None

        Returns:
            Dict[str, Any]: Collection metadata, row count, and index names.
        """

        def op():
            with self._get_cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row_count = cur.fetchone()[0]
                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                    ORDER BY indexname
                    """,
                    (self.schema_name, self.collection_name),
                )
                indexes = [row[0] for row in cur.fetchall()]
            return {
                "name": self.collection_name,
                "schema_name": self.schema_name,
                "count": row_count,
                "dimension": self.embedding_model_dims,
                "metadata_column_mode": self.metadata_column_mode,
                "payload_storage_mode": self.payload_storage_mode,
                "filter_storage_mode": self.filter_storage_mode,
                "deployment_mode": self.deployment_mode,
                "distribution_mode": self.distribution_mode,
                "vector_index_type": self.vector_index_type,
                "vector_metric": self.vector_metric,
                "bm25_enabled": self.bm25_enabled,
                "indexes": indexes,
            }

        return self._run_with_retry("col_info", op)

    def list(self, filters: Optional[dict] = None, top_k: Optional[int] = 100) -> List[List[OutputData]]:
        """
        List vectors from the collection.

        Args:
            filters (dict, optional): Filters to apply to the list operation. Defaults to None.
            top_k (int, optional): Maximum number of results to return. Defaults to 100.

        Returns:
            List[List[OutputData]]: Listed vector payloads.
        """
        where_clause, params = self._build_where_clause(filters)
        limit = 100 if top_k is None else top_k

        def op():
            with self._get_cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, payload
                    FROM {self.table_name}
                    {where_clause}
                    ORDER BY id ASC
                    LIMIT %s
                    """,
                    (*params, limit),
                )
                rows = cur.fetchall()
            return [[OutputData(id=str(row[0]), score=None, payload=self._decode_payload(row[1])) for row in rows]]

        return self._run_with_retry("list", op)

    def reset(self) -> None:
        """
        Reset the current collection by dropping and recreating it.

        Args:
            None

        Returns:
            None
        """
        logger.warning("Resetting GaussDB collection %s", self.collection_name)
        self.delete_col()
        self.create_col()

    def _build_where_clause(self, filters: Optional[dict]) -> Tuple[str, List[Any]]:
        if not filters:
            return "", []
        result = self._build_filter_expression_result(filters)
        if not result.expression:
            return "", []
        return f"WHERE {result.expression}", result.params

    def _build_filter_expression(self, filters: dict) -> Tuple[str, List[Any]]:
        result = self._build_filter_expression_result(filters)
        return result.expression, result.params

    def _build_filter_expression_result(self, filters: dict) -> _FilterBuildResult:
        if not isinstance(filters, dict):
            raise ValueError("filters must be a dictionary")
        expressions = []
        params: List[Any] = []
        for key, value in filters.items():
            normalized_key = {"$and": "AND", "$or": "OR", "$not": "NOT"}.get(key, key)
            if normalized_key in {"AND", "OR"}:
                if not isinstance(value, list):
                    raise ValueError(f"{normalized_key} filter value must be a list")
                sub_expressions = []
                for item in value:
                    result = self._build_filter_expression_result(item)
                    if result.expression:
                        sub_expressions.append(f"({result.expression})")
                        params.extend(result.params)
                if sub_expressions:
                    joiner = " AND " if normalized_key == "AND" else " OR "
                    expressions.append(f"({joiner.join(sub_expressions)})")
            elif normalized_key == "NOT":
                if not isinstance(value, list):
                    raise ValueError("NOT filter value must be a list")
                for item in value:
                    result = self._build_filter_expression_result(item)
                    if result.expression:
                        expressions.append(f"(({result.expression}) IS NOT TRUE)")
                        params.extend(result.params)
            else:
                ops_map = self._normalize_field_value(value)
                result = self._build_field_clauses(normalized_key, ops_map)
                if result.expression:
                    expressions.append(result.expression)
                    params.extend(result.params)
        return _FilterBuildResult(expression=" AND ".join(expressions), params=params)

    def _build_field_filter(self, key: str, value: Any) -> Tuple[str, List[Any]]:
        ops_map = self._normalize_field_value(value)
        result = self._build_field_clauses(key, ops_map)
        return result.expression, result.params

    def _normalize_field_value(self, value: Any) -> Dict[str, Any]:
        if isinstance(value, dict):
            return dict(value)
        if value == "*":
            return {"wildcard": True}
        if isinstance(value, list):
            return {"in": value}
        return {"eq": value}

    def _build_field_clauses(self, key: str, ops_map: Dict[str, Any]) -> _FilterBuildResult:
        self._validate_filter_key(key)
        if ops_map.get("wildcard") is True and len(ops_map) == 1:
            return _FilterBuildResult(expression="", params=[])

        ops = set(ops_map.keys())
        unsupported_ops = ops - _SUPPORTED_FILTER_OPERATORS
        if unsupported_ops:
            raise ValueError(
                f"Unsupported filter operator(s) for field {key!r}: {sorted(unsupported_ops)}. "
                f"Supported operators: {sorted(_SUPPORTED_FILTER_OPERATORS)}"
            )
        if not ops:
            raise ValueError(f"Filter operator map for field {key!r} cannot be empty")

        clauses: List[str] = []
        params: List[Any] = []
        active_range_ops = ops & _RANGE_FILTER_OPERATORS
        if active_range_ops:
            range_value = {op: ops_map[op] for op in ("gt", "gte", "lt", "lte") if op in ops_map}
            range_result = self._build_range_filter_result(key, range_value)
            clauses.append(range_result.expression)
            params.extend(range_result.params)

        for op_name in ("eq", "ne", "in", "nin", "contains", "icontains"):
            if op_name not in ops_map:
                continue
            clause_result = self._build_single_operator_clause(key, op_name, ops_map[op_name])
            clauses.append(clause_result.expression)
            params.extend(clause_result.params)

        if not clauses:
            raise ValueError(f"Filter for field {key!r} did not produce any supported SQL clause")

        return _FilterBuildResult(expression=" AND ".join(clauses), params=params)

    def _build_single_operator_clause(self, key: str, op_name: str, value: Any) -> _FilterBuildResult:
        if op_name == "eq":
            if key in self._redundant_scope_columns and isinstance(value, (list, tuple, dict)):
                raise ValueError(
                    f"Operator 'eq' on scope field {key!r} requires a scalar operand; "
                    "use 'in' for multiple values"
                )
            if key in self._redundant_scope_columns:
                field_sql, scope_params = self._field_sql(key)
                if value is None:
                    return _FilterBuildResult(expression=f"{field_sql} IS NULL", params=scope_params)
                return _FilterBuildResult(expression=f"{field_sql} = %s", params=[*scope_params, value])
            expr, expr_params = self._field_exact_expression(key, value, negate=False)
            return _FilterBuildResult(expression=expr, params=expr_params)

        if op_name == "ne":
            if key in self._redundant_scope_columns and isinstance(value, (list, tuple, dict)):
                raise ValueError(
                    f"Operator 'ne' on scope field {key!r} requires a scalar operand; "
                    "use 'nin' for multiple values"
                )
            if key in self._redundant_scope_columns:
                field_sql, scope_params = self._field_sql(key)
                if value is None:
                    return _FilterBuildResult(expression=f"{field_sql} IS NOT NULL", params=scope_params)
                return _FilterBuildResult(expression=f"({field_sql} = %s) IS NOT TRUE", params=[*scope_params, value])
            expr, expr_params = self._field_exact_expression(key, value, negate=True)
            return _FilterBuildResult(expression=expr, params=expr_params)

        if op_name in {"in", "nin"}:
            if not isinstance(value, (list, tuple)):
                raise ValueError(
                    f"Operator {op_name!r} on field {key!r} requires a list or tuple operand"
                )
            expr, expr_params = self._field_in_expression(key, list(value), negate=(op_name == "nin"))
            return _FilterBuildResult(expression=expr, params=expr_params)

        if op_name in {"contains", "icontains"}:
            if not isinstance(value, str):
                raise ValueError(
                    f"Operator {op_name!r} on field {key!r} requires a string operand"
                )
            escaped = self._escape_like(value)
            if key in self._redundant_scope_columns:
                field_sql, scope_params = self._field_sql(key)
                if op_name == "icontains":
                    expression = f"LOWER({field_sql}) LIKE LOWER(%s) ESCAPE '!'"
                else:
                    expression = f"{field_sql} LIKE %s ESCAPE '!'"
                return _FilterBuildResult(expression=expression, params=[*scope_params, f"%{escaped}%"])
            if op_name == "icontains":
                expression = (
                    "jsonb_typeof(payload->%s) = 'string' "
                    "AND LOWER(payload->>%s) LIKE LOWER(%s) ESCAPE '!'"
                )
            else:
                expression = (
                    "jsonb_typeof(payload->%s) = 'string' "
                    "AND payload->>%s LIKE %s ESCAPE '!'"
                )
            return _FilterBuildResult(expression=expression, params=[key, key, f"%{escaped}%"])

        raise ValueError(f"Unsupported filter operator {op_name!r} for field {key!r}")

    def _field_in_expression(self, key: str, values: Iterable[Any], negate: bool) -> Tuple[str, List[Any]]:
        values = list(values)
        if not values:
            return ("1 = 1" if negate else "1 = 0"), []
        if key in self._redundant_scope_columns:
            field_sql, params = self._field_sql(key)
            non_null_values = [item for item in values if item is not None]
            has_null = any(item is None for item in values)
            if not non_null_values:
                return (f"{field_sql} IS NOT NULL" if negate else f"{field_sql} IS NULL"), [*params]
            placeholders = ", ".join(["%s"] * len(non_null_values))
            in_expr = f"{field_sql} IN ({placeholders})"
            out_params: List[Any] = [*params, *non_null_values]
            if has_null:
                in_expr = f"({in_expr} OR {field_sql} IS NULL)"
            if negate:
                return f"({in_expr}) IS NOT TRUE", out_params
            return in_expr, out_params
        if len(values) == 1:
            return self._field_exact_expression(key, values[0], negate=negate)
        operator = " OR " if not negate else " AND "
        expressions = []
        params: List[Any] = []
        for item in values:
            expr, expr_params = self._field_exact_expression(key, item, negate=negate)
            expressions.append(f"({expr})")
            params.extend(expr_params)
        return f"({operator.join(expressions)})", params

    def _field_sql(self, key: str) -> Tuple[str, List[Any]]:
        if key in self._redundant_scope_columns:
            return self._quote_identifier(key), []
        return "payload->>%s", [key]

    def _field_exact_expression(self, key: str, value: Any, negate: bool) -> Tuple[str, List[Any]]:
        self._validate_filter_key(key)
        payload = self._dump_json(value, f"Filter value for field {key!r}", separators=(",", ":"))
        expression = "(payload->%s = %s::JSONB) IS NOT TRUE" if negate else "payload->%s = %s::JSONB"
        return expression, [key, payload]

    def _build_range_filter(self, key: str, value: dict) -> Tuple[str, List[Any]]:
        result = self._build_range_filter_result(key, value)
        return result.expression, result.params

    def _build_range_filter_result(self, key: str, value: dict) -> _FilterBuildResult:
        field_type = self._resolve_range_field_type(key, value)
        if field_type is None:
            raise ValueError(
                f"Range filter for field {key!r} requires all operands to be numbers "
                f"or ISO-style datetime strings; got {value!r}"
            )

        expressions = []
        params: List[Any] = []
        if field_type == "number":
            column_expr = (
                "CASE WHEN jsonb_typeof(payload->%s) = 'number' THEN CAST(payload->>%s AS DOUBLE PRECISION) END"
            )
        else:
            column_expr = (
                "CASE WHEN jsonb_typeof(payload->%s) = 'string' "
                "AND payload->>%s ~ %s "
                "THEN CAST(payload->>%s AS TIMESTAMPTZ) END"
            )
        mapping = {
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
        }
        for op_name in ("gt", "gte", "lt", "lte"):
            if op_name in value:
                if field_type == "number":
                    expressions.append(f"{column_expr} {mapping[op_name]} %s")
                    params.extend([key, key, value[op_name]])
                else:
                    expressions.append(f"{column_expr} {mapping[op_name]} %s")
                    params.extend([key, key, _ISO_8601_TIMESTAMPTZ_PATTERN, key, value[op_name]])
        if not expressions:
            raise ValueError(f"Unsupported range filter for field {key!r}")
        return _FilterBuildResult(expression=" AND ".join(expressions), params=params)

    def _resolve_range_field_type(self, key: str, value: dict) -> Optional[str]:
        range_values = [value[op] for op in ("gt", "gte", "lt", "lte") if op in value]
        if not range_values:
            return None

        if all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item))
            for item in range_values
        ):
            return "number"

        if all(self._is_iso_datetime_string(item) for item in range_values):
            return "datetime"

        return None

    @staticmethod
    def _is_iso_datetime_string(value: Any) -> bool:
        if not isinstance(value, str):
            return False
        if not _ISO_8601_DATETIME_RE.match(value):
            return False
        candidate = value[:-1] + "+00:00" if value.endswith("Z") else value
        try:
            datetime.fromisoformat(candidate)
            return True
        except ValueError:
            return False

    def close(self):
        """Explicitly release the connection pool."""
        if getattr(self, "connection_pool", None) is not None:
            try:
                self.connection_pool.closeall()
            except Exception:
                pass
            self.connection_pool = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __del__(self):
        try:
            if self.connection_pool is not None:
                self.connection_pool.closeall()
        except Exception:
            pass
