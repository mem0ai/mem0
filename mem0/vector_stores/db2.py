"""IBM Db2 vector store for mem0."""

from __future__ import annotations

import functools
import json
import logging
import re
import math
import uuid
from contextlib import contextmanager
from datetime import datetime
from typing import Any, Dict, Iterator, List, Optional, Tuple

from pydantic import BaseModel

try:
    import ibm_db_dbi
except ImportError as exc:  # pragma: no cover - optional dependency guard
    raise ImportError(
        "The 'ibm_db_dbi' library is required for the Db2 vector store. "
        "Install it with: pip install ibm_db"
    ) from exc

try:
    import numpy as np

    _HAS_NUMPY = True
except ImportError:  # pragma: no cover - optional dependency
    _HAS_NUMPY = False

from mem0.configs.vector_stores.db2 import Db2Config
from mem0.vector_stores.base import VectorStoreBase

logger = logging.getLogger(__name__)

# Minimum Db2 version for AI Vector Search.
_MIN_DB2_VERSION = (12, 1, 2)

# Minimum Db2 version for the native ANN vector index (CREATE VECTOR INDEX).
_MIN_ANN_VERSION = (12, 1, 5)

# HAMMING, MANHATTAN, and DOT are not supported by the Db2 ANN index.
_ANN_SUPPORTED_METRICS = {"COSINE", "EUCLIDEAN", "EUCLIDEAN_DISTANCE"}

# Db2's VECTOR_DISTANCE() only accepts "EUCLIDEAN" as the SQL keyword —
# "EUCLIDEAN_DISTANCE" raises SQL0104N. Map the alias before emitting SQL.
_SQL_METRIC = {
    "EUCLIDEAN_DISTANCE": "EUCLIDEAN",
}

_SCORE_FROM_DISTANCE = {
    "EUCLIDEAN":          lambda d: 1.0 / (1.0 + d),
    "EUCLIDEAN_DISTANCE": lambda d: 1.0 / (1.0 + d),
    "COSINE":             lambda d: max(0.0, 1.0 - d),
    "DOT":                lambda d: d,
    "HAMMING":            lambda d: 1.0 / (1.0 + d),
    "MANHATTAN":          lambda d: 1.0 / (1.0 + d),
}

_ORDER_BY_DIRECTION = {
    "EUCLIDEAN":          "ASC",
    "EUCLIDEAN_DISTANCE": "ASC",
    "COSINE":             "ASC",
    "DOT":                "DESC",
    "HAMMING":            "ASC",
    "MANHATTAN":          "ASC",
}

_LOGICAL_OPS = {
    "$and": "AND",
    "$or":  "OR",
    "$not": "NOT",
    "AND":  "AND",
    "OR":   "OR",
    "NOT":  "NOT",
}

_DUPLICATE_INDICATORS = (
    "sql0803n",
    "sqlstate=23505",
    "sqlcode=-803",
    "duplicate",
    "unique",
    "primary key",
)


def _distance_to_score(distance: float, strategy: str) -> float:
    fn = _SCORE_FROM_DISTANCE.get(strategy)
    if fn is None:
        raise ValueError(f"Unsupported distance strategy: '{strategy}'")
    return fn(distance)


def _handle_db_exceptions(func):
    """Decorator that re-raises DB and validation errors with context."""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (RuntimeError, ValueError, TypeError):
            raise
        except Exception as exc:
            raise RuntimeError(
                f"Db2VectorStore.{func.__name__} failed: {exc}"
            ) from exc
    return wrapper


def _normalize_filter_value(value: Any) -> str:
    """Normalise a Python value for inlining in a SQL string literal.

    Booleans in JSON are stored as ``true``/``false`` text — Python ``True``
    would otherwise be stringified as ``"True"`` (capital T) which never
    matches.  Also escapes single quotes per the SQL standard.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).replace("'", "''")


def _is_iso_date(value: Any) -> bool:
    """Return True if *value* is a string Python recognises as ISO-8601 datetime."""
    if not isinstance(value, str):
        return False
    try:
        normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
        datetime.fromisoformat(normalized)
        return True
    except ValueError:
        return False


def _cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two equal-length vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def _mmr_select_numpy(
    query_vec: List[float],
    candidate_vecs: List[List[float]],
    candidate_items: List[Any],
    k: int,
    lambda_mult: float,
) -> List[Any]:
    """Numpy-accelerated MMR selection (30–168× faster than pure Python at DIM=1536).

    Uses vectorised matrix operations for cosine similarity — identical algorithm
    and results to :func:`_mmr_select`.  Called automatically when numpy is available
    (``_HAS_NUMPY=True``); falls back to the pure-Python path otherwise.
    """
    if not candidate_items:
        return []

    mat = np.array(candidate_vecs, dtype=np.float32)
    norms = np.linalg.norm(mat, axis=1, keepdims=True)
    norms = np.where(norms == 0.0, 1.0, norms)
    mat_normed = mat / norms

    q = np.array(query_vec, dtype=np.float32)
    q_norm = np.linalg.norm(q)
    q_normed = q / q_norm if q_norm > 0.0 else q

    query_sims = mat_normed @ q_normed

    n = len(candidate_items)
    k = min(k, n)
    remaining = list(range(n))
    selected_indices: List[int] = []
    best_redundancy = np.full(n, -np.inf, dtype=np.float32)

    for _ in range(k):
        if not remaining:
            break

        rem = np.array(remaining, dtype=np.intp)

        if selected_indices:
            last = selected_indices[-1]
            new_sims = mat_normed[rem] @ mat_normed[last]
            best_redundancy[rem] = np.maximum(best_redundancy[rem], new_sims)
            redundancy = best_redundancy[rem]
        else:
            redundancy = np.zeros(len(rem), dtype=np.float32)

        scores = lambda_mult * query_sims[rem] - (1.0 - lambda_mult) * redundancy
        best_local = int(np.argmax(scores))
        best_idx = remaining[best_local]

        selected_indices.append(best_idx)
        remaining.pop(best_local)

    return [candidate_items[i] for i in selected_indices]


def _mmr_select(
    query_vec: List[float],
    candidate_vecs: List[List[float]],
    candidate_items: List[Any],
    k: int,
    lambda_mult: float,
) -> List[Any]:
    """Maximal Marginal Relevance selection.

    Iteratively picks the candidate that maximises::

        score = lambda_mult * sim(item, query) - (1 - lambda_mult) * max_sim(item, selected)

    Dispatches to :func:`_mmr_select_numpy` when numpy is available for a
    30–168× speedup at DIM=1536, otherwise uses the pure-Python loop below.

    Args:
        query_vec: The query embedding vector.
        candidate_vecs: Embedding vectors for every candidate (parallel to ``candidate_items``).
        candidate_items: Arbitrary objects corresponding to each candidate vector.
        k: Number of items to select.
        lambda_mult: Trade-off weight in [0, 1].  1.0 = pure relevance (no diversity),
            0.0 = pure diversity (no relevance).

    Returns:
        Up to *k* items from ``candidate_items``, ordered by MMR selection.
    """
    if not candidate_items:
        return []

    if _HAS_NUMPY:
        return _mmr_select_numpy(query_vec, candidate_vecs, candidate_items, k, lambda_mult)

    k = min(k, len(candidate_items))
    remaining = list(range(len(candidate_items)))
    selected_indices: List[int] = []
    selected_vecs: List[List[float]] = []

    query_sims = [_cosine_similarity(query_vec, v) for v in candidate_vecs]

    for _ in range(k):
        best_idx = -1
        best_score = float("-inf")

        for idx in remaining:
            relevance = query_sims[idx]
            if selected_vecs:
                redundancy = max(_cosine_similarity(candidate_vecs[idx], sv) for sv in selected_vecs)
            else:
                redundancy = 0.0
            mmr_score = lambda_mult * relevance - (1.0 - lambda_mult) * redundancy
            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx == -1:
            break
        selected_indices.append(best_idx)
        selected_vecs.append(candidate_vecs[best_idx])
        remaining.remove(best_idx)

    return [candidate_items[i] for i in selected_indices]


class OutputData(BaseModel):
    id: Optional[str]
    score: Optional[float]
    payload: Optional[Dict[str, Any]]


def _table_exists(client: Any, table_name: str) -> bool:
    """Check table existence via SYSCAT.TABLES — no data scan required."""
    bare = table_name.strip('"').upper()
    sql = (
        "SELECT COUNT(*) FROM SYSCAT.TABLES "  # noqa: S608
        "WHERE TABNAME = ? AND TABSCHEMA = CURRENT SCHEMA"
    )
    cursor = client.cursor()
    try:
        cursor.execute(sql, [bare])
        row = cursor.fetchone()
        return bool(row and row[0] > 0)
    finally:
        cursor.close()


def _create_table_if_not_exists(
    client: Any,
    table_name: str,
    embedding_dim: int,
    text_field: str,
    id_field: str,
    metadata_field: str,
    embedding_field: str,
    text_lemmatized_field: str,
) -> None:
    if _table_exists(client, table_name):
        logger.info("Table %s already exists.", table_name)
        return

    cols = (
        f"{id_field} VARCHAR(36) PRIMARY KEY NOT NULL, "
        f"{text_field} CLOB, "
        f"{text_lemmatized_field} CLOB, "
        f"{metadata_field} BLOB, "
        f"{embedding_field} VECTOR({embedding_dim}, FLOAT32)"
    )
    ddl = f"CREATE TABLE {table_name} ({cols})"
    cursor = client.cursor()
    try:
        cursor.execute(ddl)
        client.commit()
        logger.info("Table %s created.", table_name)
    except Exception:
        client.rollback()
        raise
    finally:
        cursor.close()


def _validate_embedding(embedding: Any, allow_none: bool = True) -> None:
    """Validate an embedding vector's type and contents.

    Args:
        embedding: Value to validate.
        allow_none: When ``True`` (default) ``None`` is accepted silently.

    Raises:
        ValueError: If the embedding is ``None`` when ``allow_none=False``,
            or is an empty list.
        TypeError: If the embedding is not a ``list``, or contains non-numeric
            values.
    """
    if embedding is None:
        if not allow_none:
            raise ValueError("Embedding cannot be None.")
        return
    if not isinstance(embedding, list):
        raise TypeError(f"Embedding must be a list, got {type(embedding).__name__}.")
    if len(embedding) == 0:
        raise ValueError("Embedding cannot be empty.")
    if not all(isinstance(x, (int, float)) for x in embedding):
        raise TypeError("All embedding values must be numeric (int or float).")


class Db2VectorStore(VectorStoreBase):
    """IBM Db2 AI Vector Search vector store.

    Supported ``distance_strategy`` values:
    ``"EUCLIDEAN"`` (default), ``"COSINE"``, ``"DOT"``,
    ``"EUCLIDEAN_DISTANCE"``, ``"HAMMING"``, ``"MANHATTAN"``.

    Args:
        collection_name: Db2 table name (created automatically if absent).
        embedding_model_dims: Dimensionality of the embedding vectors.
        client: Existing ``ibm_db_dbi.Connection`` (takes priority over
            ``connection_params``).
        connection_params: Dict with keys ``database``, ``host``, ``port``,
            ``username``, ``password`` and optionally ``security`` / ``ssl_cert``.
            When supplied without ``client``, a fresh connection is created
            via ``ibm_db_dbi.connect()`` giving this instance an isolated handle.
        distance_strategy: Distance function — ``"EUCLIDEAN"`` (default),
            ``"COSINE"``, ``"DOT"``, ``"EUCLIDEAN_DISTANCE"``,
            ``"HAMMING"``, or ``"MANHATTAN"``.
        db_schema: Optional Db2 schema name.  When set, ``SET SCHEMA <name>`` is
            issued immediately after connecting so all unqualified table
            references resolve to that schema.
        use_vector_index: When ``True`` and the Db2 server is 12.1.5+, create
            a native ANN vector index for approximate nearest-neighbour search.
            Only compatible with ``COSINE``, ``EUCLIDEAN``, and
            ``EUCLIDEAN_DISTANCE`` (validated at config time).  Defaults to
            ``False`` (exact scan, works on all versions ≥ 12.1.2).

            **Production deployments only.**  Requires Db2 12.1.5+
            Standard/Advanced Edition or Db2 on IBM Cloud/watsonx.data.
            Do **not** use with Db2 Community Edition (CE) containers
            (Podman/Docker) — CE drops TCP connections after the DDL due to
            in-memory ANN graph reconstruction, causing connection failures.
            Keep ``use_vector_index=False`` (the default) on CE containers.
        text_field: Column name for raw text (default ``"text"``).
        text_lemmatized_field: Column name for pre-processed (lemmatized) text
            (default ``"text_lemmatized"``).  Used by ``keyword_search()`` for
            higher-recall full-text matching when Db2 Text Search is installed.
        id_field: Column name for the primary key (default ``"id"``).
        metadata_field: Column name for JSON metadata (default ``"metadata"``).
        embedding_field: Column name for the stored vector (default ``"embedding"``).
    """

    def __init__(self, **kwargs: Any) -> None:
        self.config = Db2Config(**kwargs)

        # Pre-built client takes priority (test / advanced usage).
        # Otherwise build a fresh connection so each instance owns an isolated handle.
        if self.config.client is not None:
            self.client = self.config.client
        else:
            self.client = self._build_connection()

        # Version check — fail fast if Db2 is too old for AI Vector Search.
        self._db2_version: Optional[Tuple[int, int, int]] = None
        self._check_db2_version()

        self.collection_name = self.config.collection_name
        self._text_field = self.config.text_field
        self._text_lemmatized_field = self.config.text_lemmatized_field
        self._id_field = self.config.id_field
        self._metadata_field = self.config.metadata_field
        self._embedding_field = self.config.embedding_field
        self._distance_strategy = self.config.distance_strategy
        self._embedding_dim = self.config.embedding_model_dims

        # Probe once at startup whether Db2 Text Search is installed.
        self._text_search_available: bool = self._probe_text_search()

        # Probe once whether the driver supports ? bindings inside
        # JSON_VALUE(SYSTOOLS.BSON2JSON(...) RETURNING VARCHAR(1000)) predicates.
        # Falls back to inline-escaped literals automatically if the probe fails.
        self._use_param_bindings: bool = self._probe_param_bindings()

        # Ensure table exists up front so failures surface at construction time.
        _create_table_if_not_exists(
            self.client,
            self.collection_name,
            self._embedding_dim,
            self._text_field,
            self._id_field,
            self._metadata_field,
            self._embedding_field,
            self._text_lemmatized_field,
        )

        # Optionally create ANN vector index (requires 12.1.5+, opt-in via use_vector_index).
        self._maybe_create_vector_index(self.collection_name)

    def _build_connection(self) -> Any:
        """Build a fresh ``ibm_db_dbi.connect()`` connection.

        Each instance gets its own isolated handle — ``connect()`` (not
        ``pconnect()``) prevents DDL auto-commits from corrupting a shared
        pooled handle across instances.
        """
        cp = self.config.connection_params or {}
        conn_str = (
            f"DATABASE={cp.get('database')};"
            f"HOSTNAME={cp.get('host')};"
            f"PORT={cp.get('port', 50000)};"
            f"PROTOCOL=TCPIP;"
            f"UID={cp.get('username')};"
            f"PWD={cp.get('password')};"
            f"Authentication=SERVER;"
        )
        if "security" in cp:
            conn_str += f"SECURITY={cp['security']};"
            ssl_cert = cp.get("ssl_cert", "")
            if ssl_cert:
                conn_str += f"SSLServerCertificate={ssl_cert};"
        try:
            conn = ibm_db_dbi.connect(conn_str, "", "")
        except Exception as exc:
            safe = re.sub(r"PWD=[^;]*", "PWD=***", conn_str)
            raise ConnectionError(
                f"Db2 connection failed: {exc}  (conn={safe})"
            ) from exc

        if self.config.db_schema:
            cursor = conn.cursor()
            try:
                cursor.execute(f"SET SCHEMA {self.config.db_schema}")
                conn.commit()
            except Exception as exc:
                conn.rollback()
                raise RuntimeError(
                    f"Failed to set schema '{self.config.db_schema}': {exc}"
                ) from exc
            finally:
                cursor.close()

        return conn

    @contextmanager
    def _get_cursor(self, commit: bool = False) -> Iterator[Any]:
        """Yield a cursor; commit or rollback on exit; always close the cursor.

        Args:
            commit: When ``True``, call ``self.client.commit()`` on success.
                    On any exception, ``rollback()`` is attempted before
                    re-raising.
        """
        cursor = self.client.cursor()
        try:
            yield cursor
            if commit:
                self.client.commit()
        except Exception:
            try:
                self.client.rollback()
            except Exception:
                pass
            raise
        finally:
            cursor.close()

    def create_col(self, name: str, vector_size: int, distance: str) -> None:
        """Create (or verify existence of) a Db2 vector table."""
        _create_table_if_not_exists(
            self.client,
            name,
            vector_size,
            self._text_field,
            self._id_field,
            self._metadata_field,
            self._embedding_field,
            self._text_lemmatized_field,
        )
        self._maybe_create_vector_index(name)

    @_handle_db_exceptions
    def insert(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
        upsert: bool = False,
    ) -> List[str]:
        """Insert vectors (with optional payloads / ids) into the table.

        Args:
            vectors: Embedding vectors to store.
            payloads: Optional list of metadata dicts (one per vector).
            ids: Optional list of string IDs. If omitted, UUIDs are generated.
            upsert: When ``True``, use ``MERGE INTO`` so existing rows are
                updated instead of raising a duplicate-key error.
                When ``False`` (default), a plain ``INSERT`` is used; a
                duplicate primary key raises ``ValueError``.

        Returns:
            List of stored IDs.
        """
        n = len(vectors)
        if payloads is None:
            payloads = [{} for _ in range(n)]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(n)]

        for i, vec in enumerate(vectors):
            try:
                _validate_embedding(vec, allow_none=False)
            except (ValueError, TypeError) as exc:
                raise type(exc)(f"Invalid embedding at index {i}: {exc}") from exc

        embedding_len = len(vectors[0]) if vectors else self._embedding_dim

        rows = [
            (
                vid,
                "[" + ", ".join(str(v) for v in vec) + "]",
                json.dumps(meta),
                meta.get("data", ""),
                meta.get("text_lemmatized", ""),
            )
            for vid, vec, meta in zip(ids, vectors, payloads)
        ]

        if upsert:
            sql = (
                f"MERGE INTO {self.collection_name} AS t "  # noqa: S608
                f"USING (VALUES (?, VECTOR(?, {embedding_len}, FLOAT32), "
                f"SYSTOOLS.JSON2BSON(?), ?, ?)) "
                f"AS s({self._id_field}, {self._embedding_field}, "
                f"{self._metadata_field}, {self._text_field}, "
                f"{self._text_lemmatized_field}) "
                f"ON t.{self._id_field} = s.{self._id_field} "
                f"WHEN MATCHED THEN UPDATE SET "
                f"t.{self._embedding_field} = s.{self._embedding_field}, "
                f"t.{self._metadata_field} = s.{self._metadata_field}, "
                f"t.{self._text_field} = s.{self._text_field}, "
                f"t.{self._text_lemmatized_field} = s.{self._text_lemmatized_field} "
                f"WHEN NOT MATCHED THEN INSERT "
                f"({self._id_field}, {self._embedding_field}, "
                f"{self._metadata_field}, {self._text_field}, "
                f"{self._text_lemmatized_field}) "
                f"VALUES (s.{self._id_field}, s.{self._embedding_field}, "
                f"s.{self._metadata_field}, s.{self._text_field}, "
                f"s.{self._text_lemmatized_field})"
            )
            with self._get_cursor(commit=True) as cursor:
                for row in rows:
                    cursor.execute(sql, row)
        else:
            sql = (
                f"INSERT INTO {self.collection_name} "  # noqa: S608
                f"({self._id_field}, {self._embedding_field}, "
                f"{self._metadata_field}, {self._text_field}, "
                f"{self._text_lemmatized_field}) "
                f"VALUES (?, VECTOR(?, {embedding_len}, FLOAT32), SYSTOOLS.JSON2BSON(?), ?, ?)"
            )
            try:
                with self._get_cursor(commit=True) as cursor:
                    cursor.executemany(sql, rows)
            except Exception as exc:
                err = str(exc).lower()
                if any(ind in err for ind in _DUPLICATE_INDICATORS):
                    raise ValueError(
                        f"Duplicate ID detected. Use upsert=True to overwrite "
                        f"existing records. Original error: {exc}"
                    ) from exc
                raise

        return ids

    @_handle_db_exceptions
    def insert_skip_duplicates(
        self,
        vectors: List[list],
        payloads: Optional[List[Dict]] = None,
        ids: Optional[List[str]] = None,
    ) -> List[str]:
        """Insert vectors, silently skipping any IDs that already exist.

        Uses ``MERGE INTO … WHEN NOT MATCHED THEN INSERT`` — existing rows are
        left unchanged.

        Args:
            vectors: Embedding vectors to store.
            payloads: Optional list of metadata dicts (one per vector).
            ids: Optional list of string IDs. If omitted, UUIDs are generated.

        Returns:
            List of IDs that were actually inserted (subset of ``ids``).
        """
        n = len(vectors)
        if payloads is None:
            payloads = [{} for _ in range(n)]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in range(n)]

        for i, vec in enumerate(vectors):
            try:
                _validate_embedding(vec, allow_none=False)
            except (ValueError, TypeError) as exc:
                raise type(exc)(f"Invalid embedding at index {i}: {exc}") from exc

        embedding_len = len(vectors[0]) if vectors else self._embedding_dim

        sql = (
            f"MERGE INTO {self.collection_name} AS t "  # noqa: S608
            f"USING (VALUES (?, VECTOR(?, {embedding_len}, FLOAT32), "
            f"SYSTOOLS.JSON2BSON(?), ?, ?)) "
            f"AS s({self._id_field}, {self._embedding_field}, "
            f"{self._metadata_field}, {self._text_field}, "
            f"{self._text_lemmatized_field}) "
            f"ON t.{self._id_field} = s.{self._id_field} "
            f"WHEN NOT MATCHED THEN INSERT "
            f"({self._id_field}, {self._embedding_field}, "
            f"{self._metadata_field}, {self._text_field}, "
            f"{self._text_lemmatized_field}) "
            f"VALUES (s.{self._id_field}, s.{self._embedding_field}, "
            f"s.{self._metadata_field}, s.{self._text_field}, "
            f"s.{self._text_lemmatized_field})"
        )

        inserted: List[str] = []
        with self._get_cursor(commit=True) as cursor:
            for vid, vec, meta in zip(ids, vectors, payloads):
                row = (
                    vid,
                    "[" + ", ".join(str(v) for v in vec) + "]",
                    json.dumps(meta),
                    meta.get("data", ""),
                    meta.get("text_lemmatized", ""),
                )
                cursor.execute(sql, row)
                if cursor.rowcount > 0:
                    inserted.append(vid)

        return inserted

    @_handle_db_exceptions
    def search(
        self,
        query: str,
        vectors: List[list],
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """Search for the *top_k* nearest vectors."""
        if vectors and isinstance(vectors[0], (int, float)):
            embedding = vectors
        else:
            embedding = vectors[0] if vectors else []
        embedding_len = len(embedding) if embedding else self._embedding_dim

        embedding_str = "[" + ", ".join(str(v) for v in embedding) + "]"
        where_clause, filter_params = self._where_clause(filters)
        order_dir = _ORDER_BY_DIRECTION[self._distance_strategy]
        sql_metric = _SQL_METRIC.get(self._distance_strategy, self._distance_strategy)

        null_check = f"{self._embedding_field} IS NOT NULL"
        if where_clause:
            full_where = f"{where_clause} AND {null_check}"
        else:
            full_where = f"WHERE {null_check}"

        sql = (
            f"SELECT {self._id_field}, "  # noqa: S608
            f"{self._text_field}, "
            f"SYSTOOLS.BSON2JSON({self._metadata_field}), "
            f"VECTOR_DISTANCE({self._embedding_field}, "
            f"VECTOR('{embedding_str}', {embedding_len}, FLOAT32), "
            f"{sql_metric}) AS distance "
            f"FROM {self.collection_name} "
            f"{full_where} "
            f"ORDER BY distance {order_dir} "
            f"FETCH FIRST {top_k} ROWS ONLY"
        )

        try:
            with self._get_cursor() as cursor:
                cursor.execute(sql, filter_params) if filter_params else cursor.execute(sql)
                rows = cursor.fetchall()
        except Exception as exc:
            # SQL0801N: COSINE on a zero-vector causes division by zero.
            err = str(exc)
            if "SQL0801N" in err or "Division by zero" in err:
                logger.debug("search() returned empty — SQL0801N (zero-vector): %s", exc)
                return []
            raise

        results = []
        for row in rows:
            metadata = json.loads(row[2] if row[2] is not None else "{}")
            score = _distance_to_score(row[3], self._distance_strategy)
            results.append(OutputData(id=row[0], score=score, payload=metadata))
        return results

    @_handle_db_exceptions
    def mmr_search(
        self,
        query: str,
        vectors: List[list],
        top_k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filters: Optional[Dict] = None,
    ) -> List[OutputData]:
        """Maximal Marginal Relevance (MMR) search.

        Retrieves *fetch_k* candidates from Db2 via the normal similarity
        search, then re-ranks them using MMR to balance relevance and diversity.
        The final result contains at most *top_k* items.

        MMR picks each successive result to maximise::

            score = lambda_mult * sim(item, query)
                    - (1 - lambda_mult) * max_sim(item, already_selected)

        All inter-item similarities are computed as cosine similarity over the
        stored embedding vectors (fetched from the database) regardless of the
        configured ``distance_strategy`` — this is the standard MMR convention.

        Args:
            query: Original query string (passed through, not used for SQL).
            vectors: Query embedding — same format as :meth:`search`.
            top_k: Number of diverse results to return.
            fetch_k: Number of candidates to retrieve before MMR re-ranking.
                     Must be >= ``top_k``.  Larger values give MMR more to
                     choose from at the cost of extra DB work.
            lambda_mult: Diversity control in ``[0.0, 1.0]``.
                         ``1.0`` = pure relevance (same as ``search``).
                         ``0.0`` = pure diversity (maximally different results).
                         ``0.5`` (default) balances both.
            filters: Optional metadata filters — same format as :meth:`search`.

        Returns:
            Up to *top_k* :class:`OutputData` items selected by MMR.
        """
        if fetch_k < top_k:
            fetch_k = top_k

        if vectors and isinstance(vectors[0], (int, float)):
            embedding = vectors
        else:
            embedding = vectors[0] if vectors else []
        embedding_len = len(embedding) if embedding else self._embedding_dim
        embedding_str = "[" + ", ".join(str(v) for v in embedding) + "]"

        where_clause, filter_params = self._where_clause(filters)
        order_dir = _ORDER_BY_DIRECTION[self._distance_strategy]
        sql_metric = _SQL_METRIC.get(self._distance_strategy, self._distance_strategy)

        null_check = f"{self._embedding_field} IS NOT NULL"
        if where_clause:
            full_where = f"{where_clause} AND {null_check}"
        else:
            full_where = f"WHERE {null_check}"

        sql = (
            f"SELECT {self._id_field}, "  # noqa: S608
            f"{self._text_field}, "
            f"SYSTOOLS.BSON2JSON({self._metadata_field}), "
            f"VECTOR_DISTANCE({self._embedding_field}, "
            f"VECTOR('{embedding_str}', {embedding_len}, FLOAT32), "
            f"{sql_metric}) AS distance, "
            f"VECTOR_SERIALIZE({self._embedding_field}) AS emb_str "
            f"FROM {self.collection_name} "
            f"{full_where} "
            f"ORDER BY distance {order_dir} "
            f"FETCH FIRST {fetch_k} ROWS ONLY"
        )

        try:
            with self._get_cursor() as cursor:
                cursor.execute(sql, filter_params) if filter_params else cursor.execute(sql)
                rows = cursor.fetchall()
        except Exception as exc:
            # SQL0801N: COSINE on a zero-vector causes division by zero.
            err = str(exc)
            if "SQL0801N" in err or "Division by zero" in err:
                logger.debug("mmr_search() returned empty — SQL0801N (zero-vector): %s", exc)
                return []
            raise

        if not rows:
            return []

        candidate_items: List[OutputData] = []
        candidate_vecs: List[List[float]] = []

        for row in rows:
            metadata = json.loads(row[2] if row[2] is not None else "{}")
            score = _distance_to_score(row[3], self._distance_strategy)
            item = OutputData(id=row[0], score=score, payload=metadata)
            candidate_items.append(item)

            # VECTOR_SERIALIZE returns a string like "[0.1, 0.2, ...]".
            raw_emb = row[4]
            if raw_emb:
                emb_vec = [float(x) for x in raw_emb.strip("[]").split(",") if x.strip()]
            else:
                emb_vec = [0.0] * embedding_len
            candidate_vecs.append(emb_vec)

        return _mmr_select(
            query_vec=embedding,
            candidate_vecs=candidate_vecs,
            candidate_items=candidate_items,
            k=top_k,
            lambda_mult=lambda_mult,
        )

    @_handle_db_exceptions
    def mmr_search_with_scores(
        self,
        query: str,
        vectors: List[list],
        top_k: int = 5,
        fetch_k: int = 20,
        lambda_mult: float = 0.5,
        filters: Optional[Dict] = None,
    ) -> List[Tuple[OutputData, float]]:
        """MMR search returning ``(OutputData, score)`` pairs.

        Identical to :meth:`mmr_search` but returns a list of
        ``(item, score)`` tuples.

        Args:
            query: Original query string (not used for SQL).
            vectors: Query embedding.
            top_k: Number of diverse results to return.
            fetch_k: Candidate pool size before MMR re-ranking.
            lambda_mult: Diversity control in ``[0.0, 1.0]``.
            filters: Optional metadata filters.

        Returns:
            List of ``(OutputData, score)`` tuples selected by MMR.
        """
        items = self.mmr_search(
            query=query,
            vectors=vectors,
            top_k=top_k,
            fetch_k=fetch_k,
            lambda_mult=lambda_mult,
            filters=filters,
        )
        return [(item, item.score) for item in items]

    @_handle_db_exceptions
    def delete(self, vector_id: str) -> None:
        """Delete a single vector by ID."""
        sql = f"DELETE FROM {self.collection_name} WHERE {self._id_field} = ?"  # noqa: S608
        with self._get_cursor(commit=True) as cursor:
            cursor.execute(sql, [vector_id])

    @_handle_db_exceptions
    def delete_by_filter(self, filters: Dict[str, Any]) -> int:
        """Delete all rows matching *filters*.

        Args:
            filters: Metadata filter dict — same format as :meth:`search`.
                     Must be non-empty; passing ``{}`` or ``None`` raises
                     ``ValueError`` to avoid accidental full-table deletes.
                     Use :meth:`reset` or :meth:`clear` to wipe all rows.

        Returns:
            Number of rows deleted.
        """
        if not filters:
            raise ValueError(
                "filters must be non-empty for delete_by_filter(). "
                "Use reset() or clear() to delete all rows."
            )
        where_clause, filter_params = self._where_clause(filters)
        if not where_clause:
            raise ValueError(
                "The supplied filters produced an empty WHERE clause. "
                "Use reset() or clear() to delete all rows."
            )
        sql = f"DELETE FROM {self.collection_name} {where_clause}"  # noqa: S608
        with self._get_cursor(commit=True) as cursor:
            cursor.execute(sql, filter_params) if filter_params else cursor.execute(sql)
            return cursor.rowcount if cursor.rowcount is not None else 0

    @_handle_db_exceptions
    def update(
        self,
        vector_id: str,
        vector: Optional[List[float]] = None,
        payload: Optional[Dict] = None,
    ) -> None:
        """Update the embedding and/or payload of an existing record."""
        if vector is None and payload is None:
            return

        if vector is not None:
            _validate_embedding(vector, allow_none=False)

        set_parts = []
        params: List[Any] = []

        if vector is not None:
            embedding_len = len(vector)
            vec_str = "[" + ", ".join(str(v) for v in vector) + "]"
            set_parts.append(
                f"{self._embedding_field} = "
                f"VECTOR('{vec_str}', {embedding_len}, FLOAT32)"
            )

        if payload is not None:
            set_parts.append(f"{self._text_field} = ?")
            params.append(payload.get("data", ""))
            set_parts.append(f"{self._text_lemmatized_field} = ?")
            params.append(payload.get("text_lemmatized", ""))
            set_parts.append(f"{self._metadata_field} = SYSTOOLS.JSON2BSON(?)")
            params.append(json.dumps(payload))

        params.append(vector_id)
        sql = (
            f"UPDATE {self.collection_name} "  # noqa: S608
            f"SET {', '.join(set_parts)} "
            f"WHERE {self._id_field} = ?"
        )

        with self._get_cursor(commit=True) as cursor:
            cursor.execute(sql, params)

    @_handle_db_exceptions
    def get(self, vector_id: str) -> Optional[OutputData]:
        """Retrieve a single record by ID."""
        sql = (
            f"SELECT {self._id_field}, "  # noqa: S608
            f"{self._text_field}, "
            f"SYSTOOLS.BSON2JSON({self._metadata_field}) "
            f"FROM {self.collection_name} "
            f"WHERE {self._id_field} = ?"
        )

        with self._get_cursor() as cursor:
            cursor.execute(sql, [vector_id])
            row = cursor.fetchone()

        if row is None:
            return None
        metadata = json.loads(row[2] if row[2] is not None else "{}")
        return OutputData(id=row[0], score=None, payload=metadata)

    @_handle_db_exceptions
    def list_cols(self) -> List[str]:
        """Return the names of all user tables in the current schema."""
        sql = "SELECT TABNAME FROM SYSCAT.TABLES WHERE TYPE = 'T' AND TABSCHEMA = CURRENT SCHEMA"  # noqa: S608
        with self._get_cursor() as cursor:
            cursor.execute(sql)
            rows = cursor.fetchall()
        return [row[0] for row in rows]

    @_handle_db_exceptions
    def delete_col(self) -> None:
        """Drop the collection table if it exists."""
        if not _table_exists(self.client, self.collection_name):
            logger.info("Table %s not found; nothing to drop.", self.collection_name)
            return
        # DROP TABLE is DDL — auto-commits in Db2.  Commit any open transaction
        # first, execute the DDL, commit again while the cursor is still open.
        self.client.commit()
        drop_cursor = self.client.cursor()
        try:
            drop_cursor.execute(f"DROP TABLE {self.collection_name}")
            self.client.commit()
        except Exception:
            try:
                self.client.rollback()
            except Exception:
                pass
            raise
        finally:
            drop_cursor.close()
        logger.info("Table %s dropped.", self.collection_name)

    @_handle_db_exceptions
    def col_info(self) -> Dict[str, Any]:
        """Return metadata about the collection table.

        Uses a live ``COUNT(*)`` scalar subquery for ``row_count`` —
        ``SYSCAT.TABLES.CARD`` returns ``-1`` until ``RUNSTATS`` is run.
        Both the catalog lookup and the row count are fetched in a single
        SQL round-trip to minimise latency.

        Returns:
            Dict with keys ``schema``, ``table_name``, ``row_count``,
            ``embedding_model_dims``, and ``distance_strategy``.
            The last two are in-memory values requiring no extra SQL.
        """
        sql = (  # noqa: S608
            "SELECT TABSCHEMA, TABNAME, "
            f"(SELECT COUNT(*) FROM {self.collection_name}) AS row_count "
            "FROM SYSCAT.TABLES "
            "WHERE TABNAME = UPPER(?) AND TABSCHEMA = CURRENT SCHEMA"
        )
        with self._get_cursor() as cursor:
            cursor.execute(sql, [self.collection_name.strip('"')])
            row = cursor.fetchone()

        if row is None:
            raise ValueError(f"Collection '{self.collection_name}' not found.")

        return {
            "schema": row[0],
            "table_name": row[1],
            "row_count": row[2],
            "embedding_model_dims": self._embedding_dim,
            "distance_strategy": self._distance_strategy,
        }

    @_handle_db_exceptions
    def list(
        self,
        filters: Optional[Dict] = None,
        top_k: Optional[int] = 100,
    ) -> List[List[OutputData]]:
        """List records in the collection."""
        where_clause, filter_params = self._where_clause(filters)
        limit = f"FETCH FIRST {top_k} ROWS ONLY" if top_k is not None else ""

        sql = (
            f"SELECT {self._id_field}, "  # noqa: S608
            f"{self._text_field}, "
            f"SYSTOOLS.BSON2JSON({self._metadata_field}) "
            f"FROM {self.collection_name} "
            f"{where_clause} "
            f"{limit}"
        )

        with self._get_cursor() as cursor:
            cursor.execute(sql, filter_params) if filter_params else cursor.execute(sql)
            rows = cursor.fetchall()

        results = []
        for row in rows:
            metadata = json.loads(row[2] if row[2] is not None else "{}")
            results.append(OutputData(id=row[0], score=None, payload=metadata))
        return [results]

    @_handle_db_exceptions
    def reset(self) -> None:
        """Drop and recreate the collection table."""
        logger.warning("Resetting collection %s …", self.collection_name)
        self.delete_col()
        _create_table_if_not_exists(
            self.client,
            self.collection_name,
            self._embedding_dim,
            self._text_field,
            self._id_field,
            self._metadata_field,
            self._embedding_field,
            self._text_lemmatized_field,
        )
        self._maybe_create_vector_index(self.collection_name)

    @_handle_db_exceptions
    def clear(self) -> int:
        """Remove all rows from the collection using ``TRUNCATE TABLE``.

        Faster than :meth:`reset` for large tables — the table structure and
        any vector index are preserved.

        Returns:
            Number of rows that existed before truncation (from a pre-count).
        """
        count_sql = f"SELECT COUNT(*) FROM {self.collection_name}"  # noqa: S608
        with self._get_cursor() as cursor:
            cursor.execute(count_sql)
            row = cursor.fetchone()
            deleted = row[0] if row else 0

        # TRUNCATE TABLE … IMMEDIATE is DDL — auto-commits in Db2.
        # Commit before, execute the DDL, commit again while cursor is still open.
        self.client.commit()
        trunc_cursor = self.client.cursor()
        try:
            trunc_cursor.execute(f"TRUNCATE TABLE {self.collection_name} IMMEDIATE")
            self.client.commit()
        except Exception:
            try:
                self.client.rollback()
            except Exception:
                pass
            raise
        finally:
            trunc_cursor.close()

        logger.info("Table %s truncated (%d rows removed).", self.collection_name, deleted)
        return deleted

    @_handle_db_exceptions
    def keyword_search(
        self,
        query: str,
        top_k: int = 5,
        filters: Optional[Dict] = None,
    ) -> Optional[List[OutputData]]:
        """Full-text keyword search using Db2 Text Search (``CONTAINS()``).

        Searches the ``text_lemmatized`` column — the pre-processed (stemmed,
        stop-word-stripped) text populated by mem0's memory pipeline — for
        higher recall than searching raw text.  Falls back to ``None`` (which
        triggers mem0's semantic-only fallback) when:

        * Db2 Text Search addon is not installed/configured (detected at
          startup by :meth:`_probe_text_search`).
        * The Text Search index does not exist on ``text_lemmatized`` yet.

        To enable keyword search, create a Text Search index on the
        ``text_lemmatized`` column::

            CALL SYSPROC.SYSTS_CREATE(
                CURRENT SCHEMA, '<TABLE>', 'text_lemmatized',
                'MAXIMUM CHARACTERS 10000 LANGUAGE EN FORMAT NONE'
            );

        Args:
            query: The search query text (lemmatized for best results).
            top_k: Maximum number of results to return.
            filters: Optional metadata filters.

        Returns:
            List of :class:`OutputData` ordered by relevance score descending,
            or ``None`` if Db2 Text Search is not available.
        """
        if not self._text_search_available:
            return None

        esc_query = self._escape_literal(query)
        where_clause, filter_params = self._where_clause(filters)

        if where_clause:
            text_pred = (
                f"AND CONTAINS({self._text_lemmatized_field}, '{esc_query}') = 1"
            )
        else:
            text_pred = (
                f"WHERE CONTAINS({self._text_lemmatized_field}, '{esc_query}') = 1"
            )

        sql = (
            f"SELECT {self._id_field}, "  # noqa: S608
            f"{self._text_field}, "
            f"SYSTOOLS.BSON2JSON({self._metadata_field}), "
            f"SCORE({self._text_lemmatized_field}, '{esc_query}') AS relevance "
            f"FROM {self.collection_name} "
            f"{where_clause} "
            f"{text_pred} "
            f"ORDER BY relevance DESC "
            f"FETCH FIRST {top_k} ROWS ONLY"
        )

        try:
            with self._get_cursor() as cursor:
                cursor.execute(sql, filter_params) if filter_params else cursor.execute(sql)
                rows = cursor.fetchall()
        except Exception as exc:
            logger.debug(
                "keyword_search() fell back to None (Text Search unavailable): %s", exc
            )
            return None

        results = []
        for row in rows:
            metadata = json.loads(row[2] if row[2] is not None else "{}")
            score = float(row[3]) / 100.0  # normalise 0–100 → 0.0–1.0
            results.append(OutputData(id=row[0], score=score, payload=metadata))
        return results

    def close(self) -> None:
        """Close the underlying database connection."""
        try:
            self.client.close()
            logger.debug("Db2 connection closed.")
        except Exception:
            pass

    def __del__(self) -> None:
        """Best-effort connection cleanup on garbage collection."""
        try:
            self.client.close()
        except Exception:
            pass

    def _probe_text_search(self) -> bool:
        """Return ``True`` if Db2 Text Search is active on this database."""
        sql = "SELECT CONTAINS(v, 'probe') FROM (VALUES ('probe text')) AS t(v)"  # noqa: S608
        available = False
        try:
            with self._get_cursor() as cursor:
                cursor.execute(sql)
                cursor.fetchone()
                available = True
        except Exception:
            available = False

        if available:
            logger.info(
                "Db2 Text Search detected — keyword_search() enabled for %s.",
                self.collection_name,
            )
        else:
            logger.debug(
                "Db2 Text Search not installed/configured — keyword_search() will "
                "return None (mem0 will use semantic-only search)."
            )
        return available

    def _probe_param_bindings(self) -> bool:
        """Return ``True`` if the driver safely handles ``?`` bindings inside
        ``JSON_VALUE(SYSTOOLS.BSON2JSON(...) RETURNING VARCHAR(1000))`` predicates.

        Omitting ``RETURNING VARCHAR(1000)`` can cause a NULL-pointer dereference
        in ibm_db on some Db2 versions.  This probe verifies safe support at
        connect time; falls back to inline escaping if the probe fails.
        """
        probe_sql = (
            "SELECT JSON_VALUE(SYSTOOLS.BSON2JSON(v), '$.x' RETURNING VARCHAR(1000)) "
            "FROM (VALUES (SYSTOOLS.JSON2BSON('{\"x\":\"ok\"}'))) AS t(v) "
            "WHERE JSON_VALUE(SYSTOOLS.BSON2JSON(v), '$.x' RETURNING VARCHAR(1000)) = ?"
        )
        try:
            with self._get_cursor() as cursor:
                cursor.execute(probe_sql, ["ok"])
                cursor.fetchone()
            logger.debug(
                "Parameterized ? bindings supported — filter predicates will use "
                "RETURNING VARCHAR(1000) + ?."
            )
            return True
        except Exception as exc:
            logger.debug(
                "Parameterized ? bindings probe failed (%s) — falling back to "
                "inline-escaped literals for filter predicates.", exc
            )
            return False

    def _check_db2_version(self) -> None:
        """Raise ``RuntimeError`` if the connected Db2 is below ``_MIN_DB2_VERSION``."""
        sql = "SELECT SERVICE_LEVEL FROM SYSIBMADM.ENV_INST_INFO"  # noqa: S608
        with self._get_cursor() as cursor:
            cursor.execute(sql)
            row = cursor.fetchone()

        if row is None:
            logger.warning("Could not determine Db2 version — proceeding anyway.")
            return

        raw = str(row[0])
        m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", raw)
        if m is None:
            logger.warning("Could not parse Db2 version from %r — proceeding anyway.", raw)
            return

        actual: Tuple[int, int, int] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
        self._db2_version = actual

        if actual < _MIN_DB2_VERSION:
            req = ".".join(str(x) for x in _MIN_DB2_VERSION)
            act = ".".join(str(x) for x in actual)
            raise RuntimeError(
                f"IBM Db2 {req}+ is required for AI Vector Search "
                f"(connected server reports {act}).  "
                f"Please upgrade your Db2 instance."
            )
        logger.debug("Db2 version check passed: %s", raw.strip())

    def _maybe_create_vector_index(self, table_name: str) -> None:
        """Create a native ANN vector index when ``use_vector_index=True``."""
        if not self.config.use_vector_index:
            return

        if self._db2_version is None or self._db2_version < _MIN_ANN_VERSION:
            req = ".".join(str(x) for x in _MIN_ANN_VERSION)
            actual_str = (
                ".".join(str(x) for x in self._db2_version)
                if self._db2_version else "unknown"
            )
            logger.warning(
                "use_vector_index=True requires Db2 %s+ (server is %s). "
                "Falling back to exact scan — set use_vector_index=False to silence this.",
                req, actual_str,
            )
            return

        if self._distance_strategy not in _ANN_SUPPORTED_METRICS:
            return

        bare_name = table_name.strip('"')
        idx_name = f"{bare_name}_vec_idx"
        sql_metric = _SQL_METRIC.get(self._distance_strategy, self._distance_strategy)
        ddl = (
            f"CREATE VECTOR INDEX {idx_name} "
            f"ON {table_name}({self._embedding_field}) "
            f"WITH DISTANCE {sql_metric}"
        )
        try:
            with self._get_cursor(commit=True) as cursor:
                cursor.execute(ddl)
            logger.info(
                "Vector index %s created on %s (%s).",
                idx_name, table_name, sql_metric,
            )
        except Exception as exc:
            logger.warning(
                "Could not create vector index on %s: %s. "
                "If running on Db2 Community Edition, this is likely a memory "
                "resource constraint — increase the container memory limit "
                "(e.g. --memory=4g), then manually restart the Db2 instance or "
                "container and reconnect.  Alternatively, set "
                "use_vector_index=False to use exact scan (works on all versions).",
                table_name, exc,
            )

    @staticmethod
    def _escape_literal(value: str) -> str:
        """Escape a string for safe inline use in a SQL string literal.

        Only used for CONTAINS()/SCORE() in keyword_search() — ibm_db cannot
        bind ``?`` parameters inside Text Search predicates.
        """
        return str(value).replace("'", "''")

    def _where_clause(self, filters: Optional[Dict[str, Any]]) -> "Tuple[str, List[Any]]":
        """Build a WHERE clause from a filter dict.

        Returns a ``(sql_fragment, params)`` tuple for use with
        ``cursor.execute(sql, params)``.

        When ``self._use_param_bindings`` is ``True``, field values are bound
        with ``?`` inside ``JSON_VALUE(… RETURNING VARCHAR(1000))``.  When
        ``False``, values are inlined as escaped literals.

        Supports flat equality, operator dicts (eq/ne/gt/gte/lt/lte/in/nin/
        contains/icontains), wildcard ``"*"``, list shorthand (→ IN), and
        compound logical keys ``AND`` / ``OR`` / ``NOT`` (also ``$and`` /
        ``$or`` / ``$not``).

        Args:
            filters: Filter dict as passed by the mem0 Memory layer.

        Returns:
            ``(sql_fragment, params)`` where ``sql_fragment`` starts with
            ``"WHERE "`` or is ``""`` when no filters apply.
        """
        if not filters:
            return "", []
        params: List[Any] = []
        conditions = self._build_conditions(filters, params)
        sql = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        return sql, params

    def _build_conditions(self, filters: Dict[str, Any], params: List[Any]) -> List[str]:
        """Recursively translate a filter dict into SQL condition strings.

        Appends bound values to ``params`` when ``self._use_param_bindings``
        is ``True``; inlines escaped literals otherwise.
        """
        conditions: List[str] = []

        for key, value in filters.items():
            logical_op = _LOGICAL_OPS.get(key)
            if logical_op is not None:
                if logical_op == "NOT":
                    if not isinstance(value, list):
                        value = [value]
                    sub_parts: List[str] = []
                    for sub in value:
                        sub_conds = self._build_conditions(sub, params)
                        if sub_conds:
                            sub_parts.append("(" + " AND ".join(sub_conds) + ")")
                    if sub_parts:
                        conditions.append("NOT (" + " OR ".join(sub_parts) + ")")
                else:
                    if not isinstance(value, list):
                        value = [value]
                    sub_parts = []
                    for sub in value:
                        sub_conds = self._build_conditions(sub, params)
                        if sub_conds:
                            sub_parts.append("(" + " AND ".join(sub_conds) + ")")
                    if sub_parts:
                        joiner = " AND " if logical_op == "AND" else " OR "
                        conditions.append("(" + joiner.join(sub_parts) + ")")
                continue

            mf = self._metadata_field
            # RETURNING VARCHAR(1000) required for safe ? bindings.
            if self._use_param_bindings:
                json_expr = (
                    f"JSON_VALUE(SYSTOOLS.BSON2JSON({mf}), '$.{key}' RETURNING VARCHAR(1000))"
                )
            else:
                json_expr = f"JSON_VALUE(SYSTOOLS.BSON2JSON({mf}), '$.{key}')"

            if value == "*":
                continue

            if isinstance(value, dict):
                for op, op_val in value.items():
                    cond = self._op_condition(json_expr, op, op_val, params)
                    if cond:
                        conditions.append(cond)

            elif isinstance(value, list):
                if self._use_param_bindings:
                    placeholders = ", ".join("?" for _ in value)
                    params.extend(_normalize_filter_value(v) for v in value)
                    conditions.append(f"{json_expr} IN ({placeholders})")
                else:
                    escaped = ", ".join(f"'{_normalize_filter_value(v)}'" for v in value)
                    conditions.append(f"{json_expr} IN ({escaped})")

            else:
                if value is None:
                    conditions.append(f"{json_expr} IS NULL")
                elif self._use_param_bindings:
                    params.append(_normalize_filter_value(value))
                    conditions.append(f"({json_expr} IS NOT NULL AND {json_expr} = ?)")
                else:
                    conditions.append(f"{json_expr} = '{_normalize_filter_value(value)}'")

        return conditions

    def _op_condition(
        self, json_expr: str, op: str, value: Any, params: List[Any]
    ) -> str:
        """Translate a single operator dict entry into a SQL condition fragment.

        Supported operators: eq, ne, gt, gte, lt, lte, in, nin,
        contains, icontains.  ``ne`` and ``nin`` are NULL-safe.
        ISO date strings pass through as VARCHAR for range comparisons.
        """
        op = op.lower()
        use_p = self._use_param_bindings

        def _inline(v: Any) -> str:
            return f"'{_normalize_filter_value(v)}'"

        def _bind(v: Any) -> str:
            """Append value to params and return '?'."""
            params.append(_normalize_filter_value(v))
            return "?"

        _val = _bind if use_p else _inline  # noqa: E731

        if op == "eq":
            if value is None:
                return f"{json_expr} IS NULL"
            if use_p:
                params.append(_normalize_filter_value(value))
                return f"({json_expr} IS NOT NULL AND {json_expr} = ?)"
            return f"({json_expr} IS NOT NULL AND {json_expr} = {_inline(value)})"
        if op == "ne":
            if value is None:
                return f"{json_expr} IS NOT NULL"
            # NULL-safe !=: rows where the field is absent also match.
            if use_p:
                params.append(_normalize_filter_value(value))
                return f"({json_expr} IS NULL OR {json_expr} <> ?)"
            return f"({json_expr} IS NULL OR {json_expr} <> {_inline(value)})"
        if op == "gt":
            if _is_iso_date(value):
                return f"{json_expr} > {_val(value)}"
            return f"CAST({json_expr} AS DOUBLE) > {float(value)}"
        if op == "gte":
            if _is_iso_date(value):
                return f"{json_expr} >= {_val(value)}"
            return f"CAST({json_expr} AS DOUBLE) >= {float(value)}"
        if op == "lt":
            if _is_iso_date(value):
                return f"{json_expr} < {_val(value)}"
            return f"CAST({json_expr} AS DOUBLE) < {float(value)}"
        if op == "lte":
            if _is_iso_date(value):
                return f"{json_expr} <= {_val(value)}"
            return f"CAST({json_expr} AS DOUBLE) <= {float(value)}"
        if op == "in":
            if not isinstance(value, list):
                raise ValueError(
                    f"Filter operator 'in' requires a list, got {type(value).__name__}"
                )
            if use_p:
                placeholders = ", ".join("?" for _ in value)
                params.extend(_normalize_filter_value(v) for v in value)
                return f"{json_expr} IN ({placeholders})"
            escaped = ", ".join(f"'{_normalize_filter_value(v)}'" for v in value)
            return f"{json_expr} IN ({escaped})"
        if op == "nin":
            if not isinstance(value, list):
                raise ValueError(
                    f"Filter operator 'nin' requires a list, got {type(value).__name__}"
                )
            if use_p:
                placeholders = ", ".join("?" for _ in value)
                params.extend(_normalize_filter_value(v) for v in value)
                return f"({json_expr} IS NULL OR {json_expr} NOT IN ({placeholders}))"
            escaped = ", ".join(f"'{_normalize_filter_value(v)}'" for v in value)
            return f"({json_expr} IS NULL OR {json_expr} NOT IN ({escaped}))"
        if op == "contains":
            return f"{json_expr} LIKE '%{_normalize_filter_value(value)}%'"
        if op == "icontains":
            return f"LOWER({json_expr}) LIKE LOWER('%{_normalize_filter_value(value)}%')"
        raise ValueError(
            f"Unsupported filter operator '{op}'. "
            f"Supported: eq, ne, gt, gte, lt, lte, in, nin, contains, icontains"
        )
