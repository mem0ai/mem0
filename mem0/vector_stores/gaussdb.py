import hashlib
import json
import logging
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from pydantic import BaseModel

try:
    from psycopg2.extras import Json
    from psycopg2.pool import ThreadedConnectionPool
except ImportError:
    Json = None
    ThreadedConnectionPool = None

from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,62}$")
_FILTER_KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
_MEMORY_SETTING_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([A-Za-z]+)\s*$")
_ISO_8601_TIMESTAMPTZ_PATTERN = (
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
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


def _first_env(*names: str) -> Optional[str]:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return None


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[dict]


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
    GaussDB centralized A-mode Ustore vector store provider for mem0.

    The implementation uses the GaussDB official psycopg2-compatible driver API.
    It avoids psycopg3-specific APIs because GaussDB's official Python examples
    use psycopg2.
    """

    _redundant_scope_columns = ("user_id", "agent_id", "run_id")

    def __init__(
        self,
        database: str = "postgres",
        collection_name: str = "mem0",
        embedding_model_dims: int = 1536,
        user: Optional[str] = None,
        password: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[int] = None,
        connection_string: Optional[str] = None,
        minconn: int = 1,
        maxconn: int = 5,
        sslmode: Optional[str] = None,
        sslrootcert: Optional[str] = None,
        schema: str = "public",
        schema_name: Optional[str] = None,
        deployment_mode: str = "centralized",
        vector_index_type: str = "gsdiskann",
        vector_metric: str = "cosine",
        auto_create: bool = True,
        require_scoped_filters: bool = True,
        metadata_schema: Optional[Dict[str, str]] = None,
    ):
        connection_string = connection_string or _first_env("GAUSSDB_CONNECTION_STRING", "GAUSSDB_DSN", "GAUSSDB_URL")
        database = _first_env("GAUSSDB_DATABASE", "GAUSSDB_DBNAME") or database
        user = user or _first_env("GAUSSDB_USER")
        password = password or _first_env("GAUSSDB_PASSWORD")
        host = host or _first_env("GAUSSDB_HOST")
        port = port or _first_env("GAUSSDB_PORT")
        sslmode = sslmode or _first_env("GAUSSDB_SSLMODE")
        sslrootcert = sslrootcert or _first_env("GAUSSDB_SSLROOTCERT")
        schema = _first_env("GAUSSDB_SCHEMA") or schema_name or schema

        self.database = database
        self.collection_name = self._validate_identifier(collection_name, "collection_name")
        self.embedding_model_dims = self._validate_positive_int(embedding_model_dims, "embedding_model_dims")
        self.user = user
        self.password = password
        self.host = host
        self.port = int(port) if port is not None else None
        self.connection_string = connection_string
        self.minconn = self._validate_positive_int(minconn, "minconn")
        self.maxconn = self._validate_positive_int(maxconn, "maxconn")
        if self.maxconn < self.minconn:
            raise ValueError("maxconn must be >= minconn")
        self.sslmode = sslmode
        self.sslrootcert = sslrootcert
        self.deployment_mode = self._validate_choice(
            str(deployment_mode).lower(), "deployment_mode", {"centralized", "distributed"}
        )
        self.vector_index_type = self._validate_choice(
            vector_index_type.lower(), "vector_index_type", {"gsdiskann", "gsivfflat"}
        )
        self.vector_metric = self._validate_choice(vector_metric.lower(), "vector_metric", {"cosine", "l2"})

        # Derived from deployment_mode
        max_embedding_dims = 1024 if self.deployment_mode == "distributed" else 4096
        if self.embedding_model_dims > max_embedding_dims:
            raise ValueError(
                f"GaussDB {self.deployment_mode} mode supports embedding dimensions <= {max_embedding_dims}, "
                f"but embedding_model_dims={self.embedding_model_dims}."
            )
        if self.embedding_model_dims > 1024 and self.vector_index_type != "gsdiskann":
            raise ValueError(
                f"embedding_model_dims={self.embedding_model_dims} exceeds 1024; "
                f"only GsDiskANN supports >1024 dimensions. Set vector_index_type='gsdiskann'."
            )
        self.distribution_mode = "hash" if self.deployment_mode == "distributed" else "none"

        # Hardcoded internal defaults
        self.client_encoding = "UTF8"
        self.schema = self._validate_identifier(schema, "schema")
        self.table_storage = "ustore"
        self.id_column_type = "uuid"
        self.gsdiskann_subgraph_count = 1
        self.vector_index_maintenance_work_mem = "128MB"
        self.bm25_enabled = self.deployment_mode != "distributed"
        self.bm25_ranking_metric = 0
        self.bm25_ncandidates = 128
        self.bm25_dictionary = None
        self.payload_storage_mode = "jsonb"
        self.filter_storage_mode = "json_expression"
        self.metadata_column_mode = "jsonb"
        self.require_scoped_filters = bool(require_scoped_filters)
        self.scope_filter_keys = ("user_id", "agent_id", "run_id")
        self.allowed_filter_keys = None
        self.metadata_schema: Dict[str, str] = dict(metadata_schema or {})
        self.enable_observability = True
        self.slow_query_ms = 1000
        self.retry_attempts = 2
        self.retry_backoff_seconds = 0.1
        self.gaussdb_version_baseline = "506"

        self.capabilities = CapabilityReport(
            baseline=self.gaussdb_version_baseline,
            payload_storage_mode=self.payload_storage_mode,
            filter_storage_mode=self.filter_storage_mode,
            metadata_column_mode=self.metadata_column_mode,
            deployment_mode=self.deployment_mode,
            distribution_mode=self.distribution_mode,
        )
        self.metrics: Dict[str, int] = {}
        self._metrics_lock = threading.Lock()

        self._schema_prefix = f'"{self.schema}".'
        self.table_name = f'{self._schema_prefix}{self._quote_identifier(self.collection_name)}'
        self.schema_meta_table_name = f'{self._schema_prefix}{self._quote_identifier(f"{self.collection_name}_schema_meta")}'

        self.connection_pool = self._create_connection_pool()
        self._probe_capabilities()
        self._warn_if_server_encoding_is_not_utf8()

        if not self.require_scoped_filters:
            logger.warning(
                "GaussDB scope guard is disabled (require_scoped_filters=False). "
                "This is not recommended for production multi-tenant environments."
            )

        if auto_create:
            collections = self.list_cols()
            if self.collection_name not in collections:
                self.create_col(vector_size=self.embedding_model_dims, distance=self.vector_metric)

    @property
    def enable_bm25(self) -> bool:
        """Backward-compatible alias for older tests/config snippets."""
        return self.bm25_enabled

    @enable_bm25.setter
    def enable_bm25(self, value: bool) -> None:
        self.bm25_enabled = bool(value)

    @staticmethod
    def _validate_positive_int(value: int, field_name: str) -> int:
        if value <= 0:
            raise ValueError(f"{field_name} must be >= 1")
        return value

    @staticmethod
    def _validate_choice(value: str, field_name: str, choices: set[str]) -> str:
        if value not in choices:
            raise ValueError(f"{field_name} must be one of {sorted(choices)}")
        return value

    def _sync_metadata_column_mode(self) -> None:
        if self.payload_storage_mode == "text":
            self.metadata_column_mode = "text"
        elif self.filter_storage_mode == "redundant_columns":
            self.metadata_column_mode = "redundant_columns"
        else:
            self.metadata_column_mode = "jsonb"

    def _warn_if_server_encoding_is_not_utf8(self) -> None:
        conn = self.connection_pool.getconn()
        try:
            server_encoding = None
            get_parameter_status = getattr(conn, "get_parameter_status", None)
            if callable(get_parameter_status):
                value = get_parameter_status("server_encoding")
                if isinstance(value, str) and value:
                    server_encoding = value

            if server_encoding is None:
                cur = conn.cursor()
                try:
                    cur.execute("SHOW server_encoding")
                    row = cur.fetchone()
                finally:
                    cur.close()
                if row and row[0]:
                    server_encoding = row[0]
        except Exception as exc:
            logger.warning("Unable to verify GaussDB server_encoding during initialization: %s", exc)
            try:
                conn.rollback()
            except Exception:
                pass
            self.connection_pool.putconn(conn)
            return

        if not server_encoding:
            logger.warning(
                "Unable to determine GaussDB server_encoding during initialization. "
                "GaussDB mem0 deployments are recommended to use UTF8 databases."
            )
            self.connection_pool.putconn(conn)
            return

        server_encoding = str(server_encoding).upper()
        if server_encoding != "UTF8":
            logger.warning(
                "GaussDB mem0 deployments are designed and validated for UTF8 databases, "
                "but detected server_encoding=%s. client_encoding remains UTF8, "
                "and non-UTF8 databases may cause unstable text, JSON, or metadata-filter behavior.",
                server_encoding,
            )
        self.connection_pool.putconn(conn)

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
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def _create_connection_pool(self):
        if ThreadedConnectionPool is None:
            raise ImportError(
                "GaussDB vector store requires the GaussDB official psycopg2 driver package. "
                "Install the GaussDB psycopg2 wheel provided for your database version."
            )

        dsn = self._build_dsn()
        logger.info("Creating GaussDB connection pool for %s", self._sanitize_dsn(dsn))
        return ThreadedConnectionPool(minconn=self.minconn, maxconn=self.maxconn, dsn=dsn)

    def _build_dsn(self) -> str:
        if self.connection_string:
            dsn = self.connection_string
            if self.sslmode and "sslmode=" not in dsn:
                dsn = f"{dsn} sslmode={self.sslmode}"
            if self.sslrootcert and "sslrootcert=" not in dsn:
                dsn = f"{dsn} sslrootcert={self.sslrootcert}"
            return dsn

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
                "GaussDB connection requires connection_string or individual fields. "
                f"Missing: {', '.join(missing)}"
            )

        parts = {
            "dbname": self.database,
            "user": self.user,
            "password": self.password,
            "host": self.host,
            "port": str(self.port),
        }
        if self.sslmode:
            parts["sslmode"] = self.sslmode
        if self.sslrootcert:
            parts["sslrootcert"] = self.sslrootcert
        return " ".join(f"{key}={self._quote_dsn_value(value)}" for key, value in parts.items() if value is not None)

    @staticmethod
    def _quote_dsn_value(value: str) -> str:
        text = str(value)
        if re.search(r"\s|'", text):
            return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"
        return text

    @staticmethod
    def _sanitize_dsn(dsn: str) -> str:
        sanitized = re.sub(r"(password=)(('[^']*')|(\S+))", r"\1<redacted>", dsn)
        sanitized = re.sub(r"(://[^:]+:)([^@]+)(@)", r"\1<redacted>\3", sanitized)
        return sanitized

    @contextmanager
    def _get_cursor(self, commit: bool = False):
        conn = self.connection_pool.getconn()
        try:
            if self.client_encoding:
                conn.set_client_encoding(self.client_encoding)
            cur = conn.cursor()
            try:
                yield cur
                if commit:
                    conn.commit()
                else:
                    conn.rollback()
            except Exception:
                conn.rollback()
                self._increment_metric("gaussdb_error_count")
                logger.exception("GaussDB operation failed; transaction rolled back")
                raise
            finally:
                cur.close()
        finally:
            self.connection_pool.putconn(conn)

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
                self._increment_metric("gaussdb_retry_count")
                logger.warning("Retrying GaussDB operation %s after transient error: %s", operation, exc)
                time.sleep(delay)
                delay *= 2
        raise last_exc

    @staticmethod
    def _is_retryable(exc: Exception) -> bool:
        message = str(exc).lower()
        return any(fragment in message for fragment in _RETRYABLE_ERROR_FRAGMENTS)

    def _record_latency(self, operation: str, start: float, outcome: str):
        if not self.enable_observability:
            return
        elapsed_ms = (time.perf_counter() - start) * 1000
        key = f"gaussdb_{operation}_latency_ms_count"
        self._increment_metric(key)
        if elapsed_ms >= self.slow_query_ms:
            logger.warning("Slow GaussDB operation op=%s outcome=%s latency_ms=%.2f", operation, outcome, elapsed_ms)

    def _increment_metric(self, key: str):
        if self.enable_observability:
            with self._metrics_lock:
                self.metrics[key] = self.metrics.get(key, 0) + 1

    @property
    def _vector_operator(self) -> str:
        return "<+>" if self.vector_metric == "cosine" else "<->"

    @property
    def _vector_index_metric(self) -> str:
        return "COSINE" if self.vector_metric == "cosine" else "L2"

    def _id_column_sql(self) -> str:
        return "UUID" if self.id_column_type == "uuid" else "VARCHAR(36)"

    def _payload_column_sql(self) -> str:
        return "TEXT" if self.payload_storage_mode == "text" else "JSONB"

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
        # because its getquoted() uses latin-1 encoding internally, which fails
        # for non-ASCII characters. The SQL cast (::JSONB or ::TEXT) in the query
        # handles the type conversion on the server side, and client_encoding=UTF8
        # ensures the raw UTF-8 bytes are transmitted correctly even when
        # server_encoding is SQL_ASCII.
        return json.dumps(payload, ensure_ascii=False)

    @staticmethod
    def _decode_payload(payload: Any) -> dict:
        if payload is None:
            return {}
        if isinstance(payload, dict):
            return payload
        if isinstance(payload, str):
            return json.loads(payload)
        return dict(payload)

    @staticmethod
    def _vector_literal(vector: Sequence[float]) -> str:
        return "[" + ",".join(str(float(value)) for value in vector) + "]"

    def _probe_capabilities(self):
        report = CapabilityReport(
            baseline=self.gaussdb_version_baseline,
            payload_storage_mode=self.payload_storage_mode,
            filter_storage_mode=self.filter_storage_mode,
            metadata_column_mode=self.metadata_column_mode,
            deployment_mode=self.deployment_mode,
            distribution_mode=self.distribution_mode,
        )

        def probe():
            with self._get_cursor(commit=True) as cur:
                try:
                    cur.execute("SHOW enable_vectordb")
                    setting = str(cur.fetchone()[0]).lower()
                    report.vector_enabled = setting in {"on", "true", "1"}
                except Exception:
                    logger.debug(
                        "Unable to read enable_vectordb; validating vector support with DDL probe", exc_info=True
                    )
                    report.vector_enabled = True
                if not report.vector_enabled:
                    raise RuntimeError("GaussDB enable_vectordb is not enabled")

        self._run_with_retry("capability_probe", probe)

        probe_table = f'{self._schema_prefix}{self._quote_identifier(f"mem0_gdb_probe_{uuid.uuid4().hex[:8]}")}'
        try:
            with self._get_cursor(commit=True) as cur:
                cur.execute(
                    f"""
                    CREATE TABLE {probe_table} (
                        id {self._id_column_sql()} PRIMARY KEY,
                        vector FLOATVECTOR({self.embedding_model_dims}),
                        payload {self._payload_column_sql()},
                        text_lemmatized TEXT
                    ) {self._create_table_suffix_sql("id")}
                    """
                )
                report.floatvector = True
                report.uuid = self.id_column_type == "uuid"
                report.jsonb = self.payload_storage_mode == "jsonb"

                index_name = self._quote_identifier(self._index_name(f"probe_{uuid.uuid4().hex[:8]}", "vector_idx"))
                self._set_vector_index_maintenance_work_mem(cur)
                with_clause = self._vector_index_with_clause()
                cur.execute(
                    f"""
                    CREATE INDEX {index_name}
                    ON {probe_table}
                    USING {self.vector_index_type} (vector {self._vector_index_metric})
                    {with_clause}
                    """
                )
                report.vector_index = True

                if self.bm25_enabled:
                    bm25_enabled_before_probe = self.bm25_enabled
                    bm25_index = self._quote_identifier(self._index_name(f"probe_{uuid.uuid4().hex[:8]}", "bm25_idx"))
                    self._create_bm25_index(cur, probe_table, index_name=bm25_index)
                    if bm25_enabled_before_probe and self.bm25_enabled:
                        savepoint = self._quote_identifier(f"mem0_bm25_probe_{uuid.uuid4().hex[:8]}")
                        cur.execute(f"SAVEPOINT {savepoint}")
                        try:
                            cur.execute(
                                f"""
                                INSERT INTO {probe_table} (id, vector, payload, text_lemmatized)
                                VALUES (%s::{self._id_column_sql()}, %s::FLOATVECTOR, %s::{self._payload_column_sql()}, %s)
                                """,
                                (
                                    str(uuid.uuid4()),
                                    self._vector_literal([0.0] * self.embedding_model_dims),
                                    self._payload_value({"probe": True}),
                                    "probe memory",
                                ),
                            )
                            self._apply_bm25_settings(cur)
                            cur.execute(
                                f"""
                                SELECT text_lemmatized ### %s AS score
                                FROM {probe_table}
                                WHERE (text_lemmatized ### %s) > 0
                                ORDER BY score DESC
                                LIMIT 1
                                """,
                                ("probe", "probe"),
                            )
                            if cur.fetchone() is None:
                                raise RuntimeError("GaussDB BM25 probe did not return a score")
                            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                            report.bm25 = True
                        except Exception as exc:
                            try:
                                cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                            except Exception:
                                logger.debug("Failed to roll back BM25 score probe savepoint", exc_info=True)
                            logger.warning("BM25 score probe failed; keyword_search will be disabled: %s", exc)
                            self.bm25_enabled = False
                            self._increment_metric("gaussdb_fallback_count")

                if self.filter_storage_mode == "json_expression":
                    expr_index = self._quote_identifier(self._index_name(f"probe_{uuid.uuid4().hex[:8]}", "user_idx"))
                    savepoint = self._quote_identifier(f"mem0_expr_idx_probe_{uuid.uuid4().hex[:8]}")
                    cur.execute(f"SAVEPOINT {savepoint}")
                    try:
                        cur.execute(f"CREATE INDEX {expr_index} ON {probe_table} ((payload->>'user_id'))")
                        cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                        report.expression_index = True
                    except Exception as exc:
                        logger.warning(
                            "JSON expression index probe failed; metadata filters remain available without expression indexes: %s",
                            exc,
                        )
                        try:
                            cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                        except Exception:
                            logger.debug("Failed to roll back JSON expression index probe savepoint", exc_info=True)
        except Exception as exc:
            err_msg = str(exc).lower()
            if "max dimension" in err_msg or ("exceeds" in err_msg and "dimension" in err_msg):
                raise RuntimeError(
                    f"GaussDB vector dimension limit exceeded: embedding_model_dims="
                    f"{self.embedding_model_dims}. The server rejected the dimension. "
                    f"Centralized + GsDiskANN supports up to 4096; gsivfflat may have lower limits. "
                    f"Use an embedding model with fewer dimensions, or check your index type and deployment mode."
                ) from exc
            elif self.payload_storage_mode == "jsonb" and "jsonb" in err_msg:
                logger.warning("JSONB probe failed; falling back to TEXT payload and redundant scope columns: %s", exc)
                self.payload_storage_mode = "text"
                self.filter_storage_mode = "redundant_columns"
                self._sync_metadata_column_mode()
                report.payload_storage_mode = self.payload_storage_mode
                report.filter_storage_mode = self.filter_storage_mode
                report.metadata_column_mode = self.metadata_column_mode
                report.jsonb = False
                report.expression_index = False
            elif self.bm25_enabled and "bm25" in str(exc).lower():
                logger.warning("BM25 probe failed; keyword_search will be disabled: %s", exc)
                self.bm25_enabled = False
                self._increment_metric("gaussdb_fallback_count")
            else:
                raise
        finally:
            try:
                with self._get_cursor(commit=True) as cur:
                    cur.execute(f"DROP TABLE IF EXISTS {probe_table}")
            except Exception:
                logger.debug("Failed to clean up GaussDB probe table %s", probe_table, exc_info=True)
            self.capabilities = report

    def _ensure_schema(self, cur) -> None:
        """Create the target schema if it does not already exist (GaussDB lacks IF NOT EXISTS for CREATE SCHEMA)."""
        cur.execute(
            "SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name = %s",
            (self.schema,),
        )
        if cur.fetchone()[0] == 0:
            cur.execute(f'CREATE SCHEMA "{self.schema}"')

    def create_col(self, *, vector_size: int = None, distance: str = None) -> None:
        table = self.table_name
        dims = vector_size or self.embedding_model_dims
        if distance:
            self.vector_metric = self._validate_choice(distance.lower(), "distance", {"cosine", "l2"})

        def op():
            with self._get_cursor(commit=True) as cur:
                self._ensure_schema(cur)
                cur.execute(
                    f"""
                    CREATE TABLE IF NOT EXISTS {table} (
                        id {self._id_column_sql()} PRIMARY KEY,
                        vector FLOATVECTOR({dims}) NOT NULL,
                        payload {self._payload_column_sql()} NOT NULL,
                        memory TEXT,
                        text_lemmatized TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        schema_version INTEGER DEFAULT 1,
                        user_id VARCHAR(128),
                        agent_id VARCHAR(128),
                        run_id VARCHAR(128)
                    ) {self._create_table_suffix_sql("id")}
                    """
                )
                self._create_schema_meta(cur)
                self._upsert_schema_meta(cur, self.collection_name, 1)
                self._ensure_indexes(cur, table)

        return self._run_with_retry("create_col", op)

    def _create_schema_meta(self, cur):
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {self.schema_meta_table_name} (
                collection_name VARCHAR(128) PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) {self._create_table_suffix_sql("collection_name")}
            """
        )

    def _upsert_schema_meta(self, cur, collection_name: str, schema_version: int):
        cur.execute(
            f"""
            MERGE INTO {self.schema_meta_table_name} AS target
            USING (VALUES (%s, %s)) AS src (collection_name, schema_version)
            ON (target.collection_name = src.collection_name)
            WHEN MATCHED THEN
                UPDATE SET schema_version = src.schema_version, updated_at = CURRENT_TIMESTAMP
            WHEN NOT MATCHED THEN
                INSERT (collection_name, schema_version, updated_at)
                VALUES (src.collection_name, src.schema_version, CURRENT_TIMESTAMP)
            """,
            (collection_name, schema_version),
        )

    def _create_vector_index(self, cur, table: str):
        index_name = self._quote_identifier(self._index_name(self.collection_name, "vector_idx"))
        self._set_vector_index_maintenance_work_mem(cur)
        with_clause = self._vector_index_with_clause()
        cur.execute(
            f"""
            CREATE INDEX IF NOT EXISTS {index_name}
            ON {table}
            USING {self.vector_index_type} (vector {self._vector_index_metric})
            {with_clause}
            """
        )

    def _vector_index_with_clause(self) -> str:
        """Build WITH clause for vector index. High-dim GsDiskANN needs enable_vector_copy=false + subgraph_count>0."""
        if self.vector_index_type == "gsdiskann" and self.embedding_model_dims > 1024:
            return f"WITH (enable_vector_copy=false, subgraph_count={self.gsdiskann_subgraph_count})"
        return ""

    def _set_vector_index_maintenance_work_mem(self, cur):
        target_mem = self.vector_index_maintenance_work_mem
        if self.embedding_model_dims > 1024 and target_mem == "128MB":
            target_mem = "2GB"
        if not target_mem:
            return

        target_bytes = self._parse_memory_setting_bytes(target_mem)
        if target_bytes is None:
            cur.execute("SET LOCAL maintenance_work_mem = %s", (target_mem,))
            return

        try:
            cur.execute("SHOW maintenance_work_mem")
            current_row = cur.fetchone()
            current_value = current_row[0] if current_row else None
            current_bytes = self._parse_memory_setting_bytes(current_value)
        except Exception:
            logger.debug("Unable to read current maintenance_work_mem; applying provider target", exc_info=True)
            current_bytes = None

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
            "mb": 1024 ** 2,
            "mib": 1024 ** 2,
            "gb": 1024 ** 3,
            "gib": 1024 ** 3,
            "tb": 1024 ** 4,
            "tib": 1024 ** 4,
        }
        multiplier = multipliers.get(unit)
        if multiplier is None:
            return None
        return int(amount * multiplier)

    def _create_bm25_index(self, cur, table: str, index_name: Optional[str] = None):
        index_name = index_name or self._quote_identifier(self._index_name(self.collection_name, "bm25_idx"))
        savepoint = self._quote_identifier(f"mem0_bm25_{uuid.uuid4().hex[:8]}")
        cur.execute(f"SAVEPOINT {savepoint}")
        try:
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {index_name}
                ON {table}
                USING bm25 (text_lemmatized)
                WITH (storage_type='USTORE')
                """
            )
            cur.execute(f"RELEASE SAVEPOINT {savepoint}")
        except Exception:
            try:
                cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception:
                logger.debug("Failed to roll back optional BM25 index savepoint", exc_info=True)
            self.bm25_enabled = False
            self._increment_metric("gaussdb_fallback_count")
            logger.warning("BM25 index creation failed; keyword_search disabled", exc_info=True)

    def _create_filter_indexes(self, cur, table: str):
        for key in self.scope_filter_keys:
            safe_key = self._validate_filter_key(key)
            index_name = self._quote_identifier(self._index_name(self.collection_name, f"{safe_key}_idx"))
            savepoint = self._quote_identifier(f"mem0_filter_idx_{uuid.uuid4().hex[:8]}")
            cur.execute(f"SAVEPOINT {savepoint}")
            try:
                cur.execute(f"CREATE INDEX IF NOT EXISTS {index_name} ON {table} ({self._quote_identifier(safe_key)})")
                cur.execute(f"RELEASE SAVEPOINT {savepoint}")
            except Exception as exc:
                try:
                    cur.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    cur.execute(f"RELEASE SAVEPOINT {savepoint}")
                except Exception:
                    logger.debug("Failed to roll back optional filter index savepoint", exc_info=True)
                self._increment_metric("gaussdb_fallback_count")
                logger.warning("Filter index creation failed for key %s; continuing without this index: %s", safe_key, exc)

    def _ensure_indexes(self, cur, table: str):
        self._create_vector_index(cur, table)
        if self.bm25_enabled:
            self._create_bm25_index(cur, table)
        self._create_filter_indexes(cur, table)

    def insert(
        self, vectors: List[List[float]], payloads: Optional[List[Dict]] = None, ids: Optional[List[str]] = None
    ) -> None:
        payloads = [{} for _ in vectors] if payloads is None else payloads
        ids = [str(uuid.uuid4()) for _ in vectors] if ids is None else ids
        if len(vectors) != len(payloads) or len(vectors) != len(ids):
            raise ValueError("vectors, payloads, and ids must have the same length")

        rows = [
            self._insert_row(vector, payload, vector_id) for vector, payload, vector_id in zip(vectors, payloads, ids)
        ]
        if not rows:
            return None
        columns = ["id", "vector", "payload", "memory", "text_lemmatized", "schema_version", *self._redundant_scope_columns]
        update_columns = [column for column in columns if column != "id"]
        update_set_sql = ", ".join(
            f"{self._quote_identifier(column)} = src.{self._quote_identifier(column)}" for column in update_columns
        )
        update_set_sql += ", updated_at = CURRENT_TIMESTAMP"
        insert_columns_sql = ", ".join(self._quote_identifier(column) for column in columns)
        insert_columns_sql += ", updated_at"
        insert_values_sql = ", ".join(f"src.{self._quote_identifier(column)}" for column in columns)
        insert_values_sql += ", CURRENT_TIMESTAMP"
        values_sql = ", ".join([self._incoming_values_sql(columns)] * len(rows))
        src_columns_sql = ", ".join(self._quote_identifier(column) for column in columns)
        flat_params = tuple(value for row in rows for value in row)

        def op():
            with self._get_cursor(commit=True) as cur:
                # MERGE INTO: GaussDB A-mode (Oracle compatible) atomic upsert.
                # Avoids the race condition of separate UPDATE + INSERT WHERE NOT EXISTS.
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
            "schema_version": "INTEGER",
            "user_id": "VARCHAR(128)",
            "agent_id": "VARCHAR(128)",
            "run_id": "VARCHAR(128)",
        }
        placeholders = [f"%s::{casts[column]}" if column in casts else "%s" for column in columns]
        return "(" + ", ".join(placeholders) + ")"

    def _insert_row(self, vector: Sequence[float], payload: dict, vector_id: str) -> Tuple:
        payload = payload or {}
        memory = payload.get("data") or payload.get("memory")
        text_lemmatized = payload.get("text_lemmatized") or memory
        row = [
            vector_id,
            self._vector_literal(vector),
            self._payload_value(payload),
            memory,
            text_lemmatized,
            1,
        ]
        row.extend(payload.get(key) for key in self._redundant_scope_columns)
        return tuple(row)

    def search(
        self, query: str, vectors: List[float], top_k: int = 5, filters: Optional[dict] = None
    ) -> List[OutputData]:
        where_clause, params = self._build_where_clause(filters, require_scope=True)
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
            return [
                OutputData(id=str(row[0]), score=float(row[1]), payload=self._decode_payload(row[2]))
                for row in rows
            ]

        return self._run_with_retry("search", op)

    def keyword_search(self, query: str, top_k: int = 5, filters: Optional[dict] = None):
        if not self.bm25_enabled:
            return None
        if not query or not query.strip():
            return []

        where_clause, params = self._build_where_clause(filters, require_scope=True)
        prefix = " AND " if where_clause else " WHERE "

        def op():
            try:
                with self._get_cursor() as cur:
                    self._apply_bm25_settings(cur)
                    cur.execute(
                        f"""
                        SELECT id, text_lemmatized ### %s AS score, payload
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
            except Exception:
                self._increment_metric("gaussdb_fallback_count")
                logger.debug("GaussDB BM25 keyword search failed", exc_info=True)
                return None

        return self._run_with_retry("keyword_search", op)

    def _apply_bm25_settings(self, cur):
        cur.execute(f"SET LOCAL bm25_ranking_metric = {int(self.bm25_ranking_metric)}")
        cur.execute(f"SET LOCAL bm25_ncandidates = {int(self.bm25_ncandidates)}")
        cur.execute("SET LOCAL enable_seqscan = off")
        if self.bm25_dictionary:
            self._validate_identifier(self.bm25_dictionary, "bm25_dictionary")
            cur.execute(f"SET LOCAL bm25_dictionary = '{self.bm25_dictionary}'")

    def search_batch(self, queries: list, vectors_list: list, top_k: int = 1, filters: Optional[dict] = None):
        if not vectors_list:
            return []
        if len(queries) != len(vectors_list):
            raise ValueError(
                f"search_batch: queries ({len(queries)}) and vectors_list ({len(vectors_list)}) length mismatch"
            )
        where_clause, filter_params = self._build_where_clause(filters, require_scope=True)
        values_sql = ", ".join(f"({idx}, %s::FLOATVECTOR)" for idx in range(len(vectors_list)))
        vector_params = [self._vector_literal(vector) for vector in vectors_list]

        def op():
            try:
                with self._get_cursor() as cur:
                    cur.execute(
                        f"""
                        WITH query_vectors(query_index, query_vector) AS (
                            VALUES {values_sql}
                        ),
                        ranked AS (
                            SELECT
                                q.query_index,
                                id,
                                vector {self._vector_operator} q.query_vector AS distance,
                                payload,
                                ROW_NUMBER() OVER (
                                    PARTITION BY q.query_index
                                    ORDER BY vector {self._vector_operator} q.query_vector ASC, id ASC
                                ) AS rank
                            FROM query_vectors q, {self.table_name}
                            {where_clause}
                        )
                        SELECT query_index, id, distance, payload
                        FROM ranked
                        WHERE rank <= %s
                        ORDER BY query_index ASC, distance ASC, id ASC
                        """,
                        (*vector_params, *filter_params, top_k),
                    )
                    rows = cur.fetchall()
                grouped = [[] for _ in vectors_list]
                for query_index, row_id, distance, payload in rows:
                    grouped[int(query_index)].append(
                        OutputData(
                            id=str(row_id),
                            score=float(distance),
                            payload=self._decode_payload(payload),
                        )
                    )
                return grouped
            except Exception as exc:
                self._increment_metric("gaussdb_fallback_count")
                logger.warning("GaussDB native batch search failed; falling back to sequential search: %s", exc)
                return [
                    self.search(query, vectors, top_k=top_k, filters=filters)
                    for query, vectors in zip(queries, vectors_list)
                ]

        return self._run_with_retry("search_batch", op)

    def delete(self, vector_id: str) -> None:
        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(f"DELETE FROM {self.table_name} WHERE id = %s", (vector_id,))

        return self._run_with_retry("delete", op)

    def update(self, vector_id: str, vector: Optional[List[float]] = None, payload: Optional[dict] = None) -> None:
        if vector is None and payload is None:
            return None

        set_clauses = []
        params = []
        if vector is not None:
            set_clauses.append("vector = %s::FLOATVECTOR")
            params.append(self._vector_literal(vector))
        if payload is not None:
            memory = payload.get("data") or payload.get("memory")
            text_lemmatized = payload.get("text_lemmatized") or memory
            set_clauses.extend(["payload = %s", "memory = %s", "text_lemmatized = %s"])
            params.extend([self._payload_value(payload), memory, text_lemmatized])
            for key in self._redundant_scope_columns:
                if key in payload:
                    set_clauses.append(f"{self._quote_identifier(key)} = %s")
                    params.append(payload.get(key))
        set_clauses.append("updated_at = CURRENT_TIMESTAMP")
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
        def op():
            with self._get_cursor() as cur:
                cur.execute(f"SELECT id, payload FROM {self.table_name} WHERE id = %s", (vector_id,))
                row = cur.fetchone()
            if not row:
                return None
            return OutputData(id=str(row[0]), score=None, payload=self._decode_payload(row[1]))

        return self._run_with_retry("get", op)

    def list_cols(self) -> List[str]:
        def op():
            with self._get_cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = %s
                    """,
                    (self.schema,),
                )
                rows = cur.fetchall()
            return [
                row[0]
                for row in rows
                if not str(row[0]).endswith("_schema_meta") and not str(row[0]).startswith("mem0_gdb_probe_")
            ]

        return self._run_with_retry("list_cols", op)

    def delete_col(self) -> None:
        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(f"DROP TABLE IF EXISTS {self.table_name}")
                cur.execute(f"DROP TABLE IF EXISTS {self.schema_meta_table_name}")

        return self._run_with_retry("delete_col", op)

    def col_info(self) -> Dict[str, Any]:
        def op():
            with self._get_cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table_name}")
                row_count = cur.fetchone()[0]
                schema_version = self._read_schema_version(cur)
                cur.execute(
                    """
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = %s AND tablename = %s
                    ORDER BY indexname
                    """,
                    (self.schema, self.collection_name),
                )
                indexes = [row[0] for row in cur.fetchall()]
            return {
                "name": self.collection_name,
                "schema": self.schema,
                "count": row_count,
                "dimension": self.embedding_model_dims,
                "schema_version": schema_version,
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

    def _read_schema_version(self, cur) -> int:
        cur.execute(
            """
            SELECT EXISTS (
                SELECT 1
                FROM information_schema.tables
                WHERE table_schema = %s AND table_name = %s
            )
            """,
            (self.schema, f"{self.collection_name}_schema_meta"),
        )
        if not cur.fetchone()[0]:
            return 1

        cur.execute(
            f"""
            SELECT schema_version
            FROM {self.schema_meta_table_name}
            WHERE collection_name = %s
            """,
            (self.collection_name,),
        )
        row = cur.fetchone()
        return int(row[0]) if row else 1

    def list(self, filters: Optional[dict] = None, top_k: Optional[int] = 100) -> List[List[OutputData]]:
        where_clause, params = self._build_where_clause(filters, require_scope=True)
        limit = 100 if top_k is None else top_k

        def op():
            with self._get_cursor() as cur:
                cur.execute(
                    f"""
                    SELECT id, payload
                    FROM {self.table_name}
                    {where_clause}
                    ORDER BY updated_at DESC, id ASC
                    LIMIT %s
                    """,
                    (*params, limit),
                )
                rows = cur.fetchall()
            return [[OutputData(id=str(row[0]), score=None, payload=self._decode_payload(row[1])) for row in rows]]

        return self._run_with_retry("list", op)

    def reset(self) -> None:
        logger.warning("Resetting GaussDB collection %s", self.collection_name)
        self.delete_col()
        self.create_col(vector_size=self.embedding_model_dims, distance=self.vector_metric)

    def migration_dry_run(self) -> Dict[str, Any]:
        return {
            "collection_name": self.collection_name,
            "schema_version": 1,
            "payload_storage_mode": self.payload_storage_mode,
            "filter_storage_mode": self.filter_storage_mode,
            "deployment_mode": self.deployment_mode,
            "distribution_mode": self.distribution_mode,
            "planned_actions": [
                "create_schema_meta_table_if_missing",
                "ensure_text_lemmatized_column",
                "ensure_scope_columns_when_filter_storage_mode_is_redundant_columns",
                "ensure_hash_distribution_when_deployment_mode_is_distributed",
                "ensure_vector_bm25_and_filter_indexes",
            ],
            "mutates_data": False,
            "limits": [
                "v1 dry-run reports provider-managed derived-field actions only",
                "full schema diff and index rebuild planning should be handled by a dedicated migration workflow",
            ],
        }

    def backfill_derived_fields(self, dry_run: bool = True) -> Dict[str, Any]:
        if self.payload_storage_mode == "text":
            return {
                "dry_run": dry_run,
                "estimated_rows": None,
                "requires_application_recompute": True,
                "reason": "payload is stored as TEXT; JSON field extraction is not available in provider SQL",
            }
        if dry_run:
            with self._get_cursor() as cur:
                cur.execute(
                    f"""
                    SELECT COUNT(*)
                    FROM {self.table_name}
                    WHERE text_lemmatized IS NULL
                       OR text_lemmatized = ''
                       OR memory IS NULL
                    """
                )
                count = cur.fetchone()[0]
            return {"dry_run": True, "estimated_rows": count}

        def op():
            with self._get_cursor(commit=True) as cur:
                cur.execute(
                    f"""
                    UPDATE {self.table_name}
                    SET
                        memory = COALESCE(memory, payload->>'data', payload->>'memory'),
                        text_lemmatized = COALESCE(NULLIF(text_lemmatized, ''), payload->>'text_lemmatized', payload->>'data', payload->>'memory'),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE text_lemmatized IS NULL
                       OR text_lemmatized = ''
                       OR memory IS NULL
                    """
                )
                affected = cur.rowcount
            return {"dry_run": False, "affected_rows": affected}

        return self._run_with_retry("migration", op)

    def analyze(self) -> None:
        def op():
            conn = self.connection_pool.getconn()
            previous_autocommit = getattr(conn, "autocommit", False)
            try:
                if self.client_encoding:
                    conn.set_client_encoding(self.client_encoding)
                conn.autocommit = True
                cur = conn.cursor()
                try:
                    cur.execute(f"ANALYZE {self.table_name}")
                finally:
                    cur.close()
            finally:
                try:
                    conn.autocommit = previous_autocommit
                except Exception:
                    logger.debug("Failed to restore autocommit after ANALYZE", exc_info=True)
                self.connection_pool.putconn(conn)

        return self._run_with_retry("analyze", op)

    def _build_where_clause(self, filters: Optional[dict], require_scope: bool) -> Tuple[str, List[Any]]:
        if require_scope and self.require_scoped_filters and not self._has_scope_filter(filters):
            raise ValueError(
                f"GaussDB provider requires at least one scoped filter by default: {', '.join(self.scope_filter_keys)}"
            )
        if not filters:
            return "", []
        expression, params = self._build_filter_expression(filters)
        if not expression:
            return "", []
        return f"WHERE {expression}", params

    def _has_scope_filter(self, filters: Optional[dict]) -> bool:
        if not filters or not isinstance(filters, dict):
            return False
        for key, value in filters.items():
            normalized_key = {"$and": "AND", "$or": "OR", "$not": "NOT"}.get(key, key)
            if normalized_key == "AND" and isinstance(value, list):
                if any(self._has_scope_filter(item) for item in value if isinstance(item, dict)):
                    return True
            elif normalized_key == "OR" and isinstance(value, list):
                if value and all(isinstance(item, dict) and self._has_scope_filter(item) for item in value):
                    return True
            elif normalized_key == "NOT":
                continue
            elif key in self.scope_filter_keys and self._is_positive_scope_filter_value(value):
                return True
        return False

    @staticmethod
    def _is_positive_scope_filter_value(value: Any) -> bool:
        if value is None or value == "" or value == "*":
            return False
        if isinstance(value, list):
            return any(GaussDB._is_positive_scope_filter_value(item) for item in value)
        if isinstance(value, dict):
            if "eq" in value:
                return GaussDB._is_positive_scope_filter_value(value["eq"])
            if "in" in value:
                in_values = value["in"]
                if not isinstance(in_values, (list, tuple, set)):
                    return False
                return any(GaussDB._is_positive_scope_filter_value(item) for item in in_values)
            return False
        return True

    def _build_filter_expression(self, filters: dict) -> Tuple[str, List[Any]]:
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
                    expr, sub_params = self._build_filter_expression(item)
                    if expr:
                        sub_expressions.append(f"({expr})")
                        params.extend(sub_params)
                if sub_expressions:
                    joiner = " AND " if normalized_key == "AND" else " OR "
                    expressions.append(joiner.join(sub_expressions))
            elif normalized_key == "NOT":
                if not isinstance(value, list):
                    raise ValueError("NOT filter value must be a list")
                for item in value:
                    expr, sub_params = self._build_filter_expression(item)
                    if expr:
                        expressions.append(f"(({expr}) IS NOT TRUE)")
                        params.extend(sub_params)
            else:
                expr, sub_params = self._build_field_filter(normalized_key, value)
                if expr:
                    expressions.append(expr)
                    params.extend(sub_params)
        return " AND ".join(expressions), params

    def _build_field_filter(self, key: str, value: Any) -> Tuple[str, List[Any]]:
        self._validate_filter_key(key)
        if not isinstance(value, dict):
            if isinstance(value, list):
                return self._field_in_expression(key, value, negate=False)
            if value is None:
                return self._field_exact_expression(key, value, negate=False)
            if key in self.scope_filter_keys:
                field_sql, params = self._field_sql(key)
                return f"{field_sql} = %s", [*params, value]
            if value == "*":
                return "", []
            return self._field_exact_expression(key, value, negate=False)

        ops = set(value.keys())
        range_ops = {"gt", "gte", "lt", "lte"}
        if ops & range_ops:
            return self._build_range_filter(key, value)
        if ops & {"exists", "not_exists", "missing"}:
            return self._build_presence_filter(key, value)
        if "eq" in value:
            return self._build_field_filter(key, value["eq"])
        if "ne" in value:
            if key in self.scope_filter_keys:
                field_sql, params = self._field_sql(key)
                return f"{field_sql} <> %s", [*params, value["ne"]]
            return self._field_exact_expression(key, value["ne"], negate=True)
        if "in" in value:
            return self._field_in_expression(key, value["in"], negate=False)
        if "nin" in value:
            return self._field_in_expression(key, value["nin"], negate=True)
        if "contains" in value or "icontains" in value:
            op = "icontains" if "icontains" in value else "contains"
            field_sql, params = self._field_sql(key)
            escaped = self._escape_like(value[op])
            if op == "icontains":
                expression = f"LOWER({field_sql}) LIKE LOWER(%s) ESCAPE '\\'"
            else:
                expression = f"{field_sql} LIKE %s ESCAPE '\\'"
            return expression, [*params, f"%{escaped}%"]
        raise ValueError(f"Unsupported filter operator(s) for field {key!r}: {sorted(ops)}")

    def _field_in_expression(self, key: str, values: Iterable[Any], negate: bool) -> Tuple[str, List[Any]]:
        values = list(values)
        if not values:
            return ("1 = 1" if negate else "1 = 0"), []
        if key in self.scope_filter_keys:
            field_sql, params = self._field_sql(key)
            placeholders = ", ".join(["%s"] * len(values))
            operator = "NOT IN" if negate else "IN"
            return f"{field_sql} {operator} ({placeholders})", [*params, *values]
        if len(values) == 1:
            return self._field_exact_expression(key, values[0], negate=negate)
        operator = " OR " if not negate else " AND "
        expressions = []
        params: List[Any] = []
        for item in values:
            expr, expr_params = self._field_exact_expression(key, item, negate=negate)
            expressions.append(f"({expr})")
            params.extend(expr_params)
        return operator.join(expressions), params

    def _field_sql(self, key: str) -> Tuple[str, List[Any]]:
        if key in self._redundant_scope_columns:
            return self._quote_identifier(key), []
        if self.filter_storage_mode == "json_expression":
            self._validate_filter_key(key)
            return f"payload->>'{key}'", []
        raise ValueError(
            f"Filter key {key!r} is not available in filter_storage_mode={self.filter_storage_mode!r}; "
            "use redundant_columns for scoped filters or json_expression for payload filters."
        )

    def _field_exact_expression(self, key: str, value: Any, negate: bool) -> Tuple[str, List[Any]]:
        self._validate_filter_key(key)
        payload = json.dumps({key: value}, ensure_ascii=False, separators=(",", ":"))
        expression = "(payload @> %s::JSONB) IS NOT TRUE" if negate else "payload @> %s::JSONB"
        return expression, [payload]

    def _build_presence_filter(self, key: str, value: dict) -> Tuple[str, List[Any]]:
        self._validate_filter_key(key)
        if len(value) != 1:
            raise ValueError(
                f"Presence filter for field {key!r} must specify exactly one of exists/not_exists/missing."
            )
        operator, raw_flag = next(iter(value.items()))
        if not isinstance(raw_flag, bool):
            raise ValueError(f"Presence filter {operator!r} for field {key!r} must be a boolean.")

        if operator == "exists":
            exists = raw_flag
        elif operator in {"not_exists", "missing"}:
            exists = not raw_flag
        else:
            raise ValueError(f"Unsupported presence filter operator for field {key!r}: {operator!r}")

        expression = "payload ? %s" if exists else "(payload ? %s) IS NOT TRUE"
        return expression, [key]

    def _build_range_filter(self, key: str, value: dict) -> Tuple[str, List[Any]]:
        field_type = self.metadata_schema.get(key)
        if field_type not in {"number", "datetime"}:
            logger.warning(
                "Range filter operators on field %r do not have a declared number/datetime metadata type; "
                "falling back to literal compatibility matching.",
                key,
            )
            return self._field_exact_expression(key, value, negate=False)

        expressions = []
        params: List[Any] = []
        if field_type == "number":
            column_expr = (
                f"CASE WHEN jsonb_typeof(payload->'{key}') = 'number' "
                f"THEN CAST(payload->>'{key}' AS DOUBLE PRECISION) END"
            )
        else:
            column_expr = (
                f"CASE WHEN jsonb_typeof(payload->'{key}') = 'string' "
                f"AND payload->>'{key}' ~ %s "
                f"THEN CAST(payload->>'{key}' AS TIMESTAMPTZ) END"
            )
            params.append(_ISO_8601_TIMESTAMPTZ_PATTERN)
        mapping = {
            "gt": ">",
            "gte": ">=",
            "lt": "<",
            "lte": "<=",
        }
        for op_name in ("gt", "gte", "lt", "lte"):
            if op_name in value:
                expressions.append(f"{column_expr} {mapping[op_name]} %s")
                params.append(value[op_name])
        if not expressions:
            raise ValueError(f"Unsupported range filter for field {key!r}")
        return " AND ".join(expressions), params

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
