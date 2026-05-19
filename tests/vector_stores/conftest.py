"""
Shared test infrastructure for GaussDB vector store tests.

Provides:
- Environment variable reading (GAUSSDB_TEST_*)
- Layered fixtures: gaussdb_p0_db, gaussdb_p1_db, gaussdb_p2_performance, gaussdb_p2_concurrent
- pytest mark registration: p0, p1, p2, slow, high_pressure
- Helper functions: _new_collection_name, _assert_exact_ids, _insert_memories,
  _concurrent_runner, _measure_latency
- Reusable FakeEmbedder and env config builder
"""

import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple

import pytest

pytest.importorskip("psycopg2", reason="GaussDB tests require psycopg2-compatible driver")

from mem0.vector_stores.gaussdb import GaussDB, OutputData  # noqa: E402


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EMBEDDING_DIMS = 3

# Deterministic test vectors (3-dimensional)
VECTOR_COFFEE = [0.10, 0.20, 0.30]
VECTOR_FLIGHT = [0.90, 0.10, 0.10]
VECTOR_WINDOW = [0.20, 0.80, 0.20]
VECTOR_AISLE = [0.20, 0.20, 0.80]
VECTOR_ZERO = [0.0, 0.0, 0.0]
VECTOR_UNIT_X = [1.0, 0.0, 0.0]
VECTOR_UNIT_Y = [0.0, 1.0, 0.0]
VECTOR_UNIT_Z = [0.0, 0.0, 1.0]
VECTOR_NEGATIVE = [-0.5, -0.5, -0.5]
VECTOR_LARGE = [999.0, 999.0, 999.0]


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _env_bool(name: str, default: bool = False) -> bool:
    """Parse boolean environment variable."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _new_collection_name(prefix: str = "mem0_test") -> str:
    """Generate a unique collection name for test isolation."""
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _gaussdb_env_config(collection_name: str, **overrides) -> Optional[Dict[str, Any]]:
    """
    Build GaussDB config dict from GAUSSDB_TEST_* environment variables.
    Returns None if required env vars are missing.
    """
    dsn = os.getenv("GAUSSDB_TEST_DSN")
    if dsn:
        config = {"connection_string": dsn}
    else:
        required = {
            "host": os.getenv("GAUSSDB_TEST_HOST"),
            "port": os.getenv("GAUSSDB_TEST_PORT"),
            "database": os.getenv("GAUSSDB_TEST_DATABASE"),
            "user": os.getenv("GAUSSDB_TEST_USER"),
            "password": os.getenv("GAUSSDB_TEST_PASSWORD"),
        }
        if not all(required.values()):
            return None
        config = {
            "host": required["host"],
            "port": int(required["port"]),
            "database": required["database"],
            "user": required["user"],
            "password": required["password"],
        }

    optional_env = {
        "sslmode": os.getenv("GAUSSDB_TEST_SSLMODE"),
        "sslrootcert": os.getenv("GAUSSDB_TEST_SSLROOTCERT"),
    }
    config.update({key: value for key, value in optional_env.items() if value})
    config.update(
        {
            "collection_name": collection_name,
            "embedding_model_dims": EMBEDDING_DIMS,
            "vector_index_type": os.getenv("GAUSSDB_TEST_VECTOR_INDEX", "gsdiskann"),
            "deployment_mode": os.getenv("GAUSSDB_TEST_DEPLOYMENT_MODE", "centralized"),
            "auto_create": True,
        }
    )
    config.update({key: value for key, value in overrides.items() if value is not None})
    return config


def gaussdb_available() -> bool:
    """Check if GaussDB test environment is configured."""
    return _gaussdb_env_config("probe") is not None


# ---------------------------------------------------------------------------
# FakeEmbedder
# ---------------------------------------------------------------------------


class FakeEmbedder:
    """Deterministic embedder for testing."""

    def embed(self, text, memory_action=None):
        normalized = str(text).lower()
        if "aisle" in normalized:
            return VECTOR_AISLE
        if "window" in normalized:
            return VECTOR_WINDOW
        if "flight" in normalized:
            return VECTOR_FLIGHT
        return VECTOR_COFFEE

    def embed_batch(self, texts, memory_action="add"):
        return [self.embed(text, memory_action) for text in texts]


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------


def _uuid(suffix: int) -> str:
    """Generate a deterministic UUID from a numeric suffix."""
    return f"00000000-0000-0000-0000-{suffix:012d}"


def _ids(rows: List[OutputData]) -> List[str]:
    """Extract IDs from OutputData rows."""
    return [str(row.id) for row in rows]


def _assert_exact_ids(rows: List[OutputData], expected_ids: set) -> None:
    """Assert that rows contain exactly the expected IDs (order-independent)."""
    assert set(_ids(rows)) == {str(eid) for eid in expected_ids}


def _assert_ordered_ids(rows: List[OutputData], expected_ids: list) -> None:
    """Assert that rows contain exactly the expected IDs in order."""
    assert _ids(rows) == [str(eid) for eid in expected_ids]


def _list_flat(db, filters=None, top_k=100) -> List[OutputData]:
    """Call db.list() and flatten the nested result to a flat list of OutputData."""
    result = db.list(filters=filters, top_k=top_k)
    if result and isinstance(result[0], list):
        return [item for sublist in result for item in sublist]
    return result


# ---------------------------------------------------------------------------
# Data insertion helpers
# ---------------------------------------------------------------------------


def _insert_memories(db: GaussDB, records: List[Tuple[str, List[float], dict]]) -> None:
    """Insert a batch of (id, vector, payload) records."""
    db.insert(
        ids=[record_id for record_id, _, _ in records],
        vectors=[vector for _, vector, _ in records],
        payloads=[payload for _, _, payload in records],
    )


def _make_payload(data: str, user_id: str = "test_user", **extra) -> dict:
    """Create a standard payload dict."""
    payload = {
        "data": data,
        "text_lemmatized": data.lower(),
        "user_id": user_id,
    }
    payload.update(extra)
    return payload


# ---------------------------------------------------------------------------
# Database factory
# ---------------------------------------------------------------------------


def _new_db(collection_name: Optional[str] = None, prefix: str = "mem0_test", **overrides) -> GaussDB:
    """Create a new GaussDB instance with a unique collection."""
    config = _gaussdb_env_config(collection_name or _new_collection_name(prefix), **overrides)
    assert config is not None, "GaussDB test environment not configured"
    return GaussDB(**config)


@contextmanager
def _managed_db(prefix: str = "mem0_test", **overrides):
    """Context manager that creates a GaussDB instance and cleans up on exit."""
    db = _new_db(prefix=prefix, **overrides)
    try:
        yield db
    finally:
        try:
            db.delete_col()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Performance measurement helpers
# ---------------------------------------------------------------------------


def _measure_latency(func: Callable, iterations: int = 10) -> Dict[str, float]:
    """
    Measure latency of a function over multiple iterations.
    Returns dict with p50, p99, min, max, mean in milliseconds.
    """
    latencies = []
    for _ in range(iterations):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)

    latencies.sort()
    n = len(latencies)
    return {
        "min_ms": latencies[0],
        "max_ms": latencies[-1],
        "mean_ms": sum(latencies) / n,
        "p50_ms": latencies[n // 2],
        "p99_ms": latencies[int(n * 0.99)] if n >= 100 else latencies[-1],
        "iterations": n,
    }


# ---------------------------------------------------------------------------
# Concurrency helpers
# ---------------------------------------------------------------------------


def _concurrent_runner(
    func: Callable,
    num_threads: int = 10,
    iterations_per_thread: int = 10,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    Run a function concurrently across multiple threads.
    Returns dict with success_count, error_count, errors, duration_ms.
    """
    errors = []
    success_count = 0
    start = time.perf_counter()

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = []
        for thread_idx in range(num_threads):
            for iter_idx in range(iterations_per_thread):
                futures.append(executor.submit(func, thread_idx, iter_idx))

        for future in as_completed(futures, timeout=timeout):
            try:
                future.result()
                success_count += 1
            except Exception as exc:
                errors.append(str(exc))

    duration_ms = (time.perf_counter() - start) * 1000
    return {
        "success_count": success_count,
        "error_count": len(errors),
        "errors": errors[:10],  # limit error list
        "duration_ms": duration_ms,
        "total_operations": num_threads * iterations_per_thread,
    }


# ---------------------------------------------------------------------------
# pytest marks registration
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom pytest markers."""
    config.addinivalue_line("markers", "p0: Priority 0 - core functionality smoke tests")
    config.addinivalue_line("markers", "p1: Priority 1 - comprehensive coverage tests")
    config.addinivalue_line("markers", "p2: Priority 2 - performance and stress tests")
    config.addinivalue_line("markers", "slow: Tests that take significant time to run")
    config.addinivalue_line("markers", "high_pressure: High-pressure stress tests")
    config.addinivalue_line("markers", "bm25: Tests requiring BM25 support")
    config.addinivalue_line("markers", "gaussdb_features: GaussDB-specific feature tests")


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_SKIP_REASON = "Set GAUSSDB_TEST_DSN or all of GAUSSDB_TEST_HOST/PORT/DATABASE/USER/PASSWORD to run GaussDB live tests"


@pytest.fixture
def gaussdb_p1_db():
    """Fixture providing a GaussDB instance for P1 tests with automatic cleanup."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_p1")
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_p1_db_json_expression():
    """Fixture providing a GaussDB instance with json_expression filter mode (now the only mode)."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_p1_json")
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_p1_db_redundant():
    """Fixture providing a GaussDB instance (redundant_columns mode removed, uses json_expression)."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_p1_red")
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_p2_performance():
    """Fixture providing a GaussDB instance for performance tests."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_p2_perf")
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_p2_concurrent():
    """Fixture providing a GaussDB instance for concurrency tests."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_p2_conc", maxconn=20)
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_bm25_db():
    """Fixture providing a GaussDB instance with BM25 enabled."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    if not _env_bool("GAUSSDB_TEST_RUN_BM25"):
        pytest.skip("Set GAUSSDB_TEST_RUN_BM25=true to run BM25 tests")
    db = _new_db(
        prefix="mem0_bm25",
    )
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


@pytest.fixture
def gaussdb_features_db():
    """Fixture providing a GaussDB instance for feature verification tests."""
    if not gaussdb_available():
        pytest.skip(_SKIP_REASON)
    db = _new_db(prefix="mem0_feat")
    yield db
    try:
        db.delete_col()
    except Exception:
        pass
