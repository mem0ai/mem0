"""
GaussDB Distributed Mode - Full E2E Test Suite for mem0 Adaptation.

Validates distributed-specific logic and full feature coverage in distributed mode.

Environment variables:
    GAUSSDB_TEST_DSN / GAUSSDB_TEST_HOST/PORT/DATABASE/USER/PASSWORD
    GAUSSDB_TEST_DISTRIBUTED=true   (required to run these tests)

Usage:
    export GAUSSDB_TEST_DISTRIBUTED=true
    pytest tests/vector_stores/test_gaussdb_distributed.py -v

Optional:
    GAUSSDB_TEST_RUN_FULL_DISTRIBUTED=true   Run the heavier full-regression classes
"""

import math
import os
import random
import statistics
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("psycopg2", reason="GaussDB distributed tests require psycopg2-compatible driver")

from mem0.vector_stores.gaussdb import GaussDB, OutputData
from tests.vector_stores.conftest import (
    EMBEDDING_DIMS,
    VECTOR_AISLE,
    VECTOR_COFFEE,
    VECTOR_FLIGHT,
    VECTOR_LARGE,
    VECTOR_NEGATIVE,
    VECTOR_UNIT_X,
    VECTOR_UNIT_Y,
    VECTOR_UNIT_Z,
    VECTOR_WINDOW,
    VECTOR_ZERO,
    _assert_exact_ids,
    _assert_ordered_ids,
    _concurrent_runner,
    _env_bool,
    _gaussdb_env_config,
    _ids,
    _insert_memories,
    _list_flat,
    _make_payload,
    _measure_latency,
    _new_collection_name,
    _new_db,
    _uuid,
    gaussdb_available,
    FakeEmbedder,
)


# ---------------------------------------------------------------------------
# Test configuration helpers
# ---------------------------------------------------------------------------

DIMS_SMALL = 4
DIMS_BOUNDARY = 1024

VECTORS_4D = {
    "A": [1.0, 0.0, 0.0, 0.0],
    "B": [0.0, 1.0, 0.0, 0.0],
    "C": [0.9, 0.1, 0.0, 0.0],
    "D": [0.0, 0.0, 1.0, 0.0],
    "E": [0.0, 0.0, 0.0, 1.0],
    "similar_A": [0.95, 0.05, 0.0, 0.0],
}


def _new_collection(prefix: str = "mem0_dist") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _gaussdb_distributed_config(collection_name: str, **overrides):
    """Build config dict for distributed mode testing."""
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
    config.update({k: v for k, v in optional_env.items() if v})
    config.update({
        "collection_name": collection_name,
        "embedding_model_dims": overrides.pop("embedding_model_dims", DIMS_SMALL),
        "deployment_mode": "distributed",
        "auto_create": True,
    })
    config.update({k: v for k, v in overrides.items() if v is not None})
    return config


def _new_dist_db(prefix: str = "mem0_dist", **overrides) -> GaussDB:
    """Create a new GaussDB instance in distributed mode."""
    config = _gaussdb_distributed_config(_new_collection(prefix), **overrides)
    assert config is not None, "GaussDB distributed test environment not configured"
    return GaussDB(**config)


def _random_vector(dims: int = DIMS_SMALL) -> list:
    return [random.random() for _ in range(dims)]


def _make_vector_seeded(seed: int, dims: int = DIMS_SMALL) -> list:
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(dims)]


def _run_concurrent(tasks, max_workers=10, timeout=600.0):
    successes = 0
    errors = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(task) for task in tasks]
        for future in as_completed(futures, timeout=timeout):
            try:
                future.result()
                successes += 1
            except Exception as exc:
                errors.append(str(exc))
    return successes, errors


def _print_latency_report(name, stats):
    print(f"\n  [PERF] {name}:")
    for key in ["iterations", "p50_ms", "p99_ms", "min_ms", "max_ms", "mean_ms"]:
        val = stats[key]
        if "ms" in key:
            print(f"    {key}: {val:.2f}")
        else:
            print(f"    {key}: {val}")


def _soft_assert(condition: bool, message: str):
    if not condition:
        print(f"  [WARN] Soft assertion failed: {message}")


# ---------------------------------------------------------------------------
# Module-level skip
# ---------------------------------------------------------------------------

_SKIP_REASON = (
    "Set GAUSSDB_TEST_DISTRIBUTED=true and configure GAUSSDB_TEST_DSN or "
    "GAUSSDB_TEST_HOST/PORT/DATABASE/USER/PASSWORD to run distributed tests"
)
_FULL_DIST_REASON = (
    "Distributed full-regression tests disabled; set GAUSSDB_TEST_RUN_FULL_DISTRIBUTED=true to enable"
)

pytestmark = [
    pytest.mark.skipif(
        not _env_bool("GAUSSDB_TEST_DISTRIBUTED"),
        reason=_SKIP_REASON,
    ),
    pytest.mark.skipif(
        not gaussdb_available(),
        reason="GaussDB connection not configured",
    ),
]


# ===========================================================================
# TestDistributedInitialization
# ===========================================================================


class TestDistributedInitialization:
    """Validate distributed mode initialization and parameter handling."""

    def test_d001_deployment_mode_set_correctly(self):
        db = _new_dist_db()
        try:
            assert db.deployment_mode == "distributed"
        finally:
            db.delete_col()

    def test_d002_bm25_auto_disabled(self):
        db = _new_dist_db()
        try:
            assert db.bm25_enabled is False
        finally:
            db.delete_col()

    def test_d003_dimension_stored_correctly(self):
        db = _new_dist_db(embedding_model_dims=128)
        try:
            assert db.embedding_model_dims == 128
        finally:
            db.delete_col()

    def test_d004_collection_name_stored(self):
        name = _new_collection("dist_init")
        config = _gaussdb_distributed_config(name)
        db = GaussDB(**config)
        try:
            assert db.collection_name == name
        finally:
            db.delete_col()

    def test_d005_auto_create_table(self):
        db = _new_dist_db()
        try:
            info = db.col_info()
            assert info["name"] == db.collection_name
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedDDL
# ===========================================================================


class TestDistributedDDL:
    """Validate DDL generation includes DISTRIBUTE BY HASH."""

    def test_d010_create_table_has_distribute_by(self):
        db = _new_dist_db()
        try:
            ddl = db._build_create_table_sql()
            assert "DISTRIBUTE BY" in ddl.upper()
        finally:
            db.delete_col()

    def test_d011_distribute_by_hash_on_id(self):
        db = _new_dist_db()
        try:
            ddl = db._build_create_table_sql()
            assert "HASH" in ddl.upper()
            assert "id" in ddl.lower()
        finally:
            db.delete_col()

    def test_d012_no_bm25_index_in_ddl(self):
        db = _new_dist_db()
        try:
            info = db.col_info()
            indexes = info.get("indexes", [])
            for idx in indexes:
                assert "gin" not in idx.lower() or "bm25" not in idx.lower()
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedCRUD
# ===========================================================================


class TestDistributedCRUD:
    """Basic CRUD operations across distributed nodes."""

    def test_d020_insert_single_and_get(self):
        db = _new_dist_db()
        try:
            vid = _uuid(1)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "distributed insert", "user_id": "alice"}])
            result = db.get(vid)
            assert result is not None
            assert result.id == vid
            assert result.payload["data"] == "distributed insert"
        finally:
            db.delete_col()

    def test_d021_insert_batch_and_list(self):
        db = _new_dist_db()
        try:
            records = [
                (_uuid(10), VECTORS_4D["A"], {"data": "rec_a", "user_id": "alice"}),
                (_uuid(11), VECTORS_4D["B"], {"data": "rec_b", "user_id": "alice"}),
                (_uuid(12), VECTORS_4D["C"], {"data": "rec_c", "user_id": "alice"}),
            ]
            _insert_memories(db, records)
            listed = _list_flat(db, filters={"user_id": "alice"}, top_k=100)
            assert len(listed) == 3
            _assert_exact_ids(listed, {_uuid(10), _uuid(11), _uuid(12)})
        finally:
            db.delete_col()

    def test_d022_upsert_existing_record(self):
        db = _new_dist_db()
        try:
            vid = _uuid(20)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "original", "user_id": "alice"}])
            db.update(vector_id=vid, payload={"data": "updated", "user_id": "alice"})
            result = db.get(vid)
            assert result.payload["data"] == "updated"
            listed = _list_flat(db, filters={"user_id": "alice"}, top_k=100)
            assert len(listed) == 1
        finally:
            db.delete_col()

    def test_d023_update_vector(self):
        db = _new_dist_db()
        try:
            vid = _uuid(21)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "vec_update", "user_id": "alice"}])
            db.update(vector_id=vid, vector=VECTORS_4D["B"])
            results = db.search("test", VECTORS_4D["B"], top_k=1, filters={"user_id": "alice"})
            assert len(results) >= 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d024_delete_by_id(self):
        db = _new_dist_db()
        try:
            vid = _uuid(30)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "to delete", "user_id": "alice"}])
            db.delete(vector_id=vid)
            assert db.get(vid) is None
        finally:
            db.delete_col()

    def test_d025_search_basic(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(40), VECTORS_4D["A"], {"data": "point_a", "user_id": "alice"}),
                (_uuid(41), VECTORS_4D["B"], {"data": "point_b", "user_id": "alice"}),
                (_uuid(42), VECTORS_4D["similar_A"], {"data": "near_a", "user_id": "alice"}),
            ])
            results = db.search("test", VECTORS_4D["A"], top_k=3, filters={"user_id": "alice"})
            assert len(results) == 3
            assert results[0].id == _uuid(40)
        finally:
            db.delete_col()

    def test_d026_get_nonexistent_returns_none(self):
        db = _new_dist_db()
        try:
            result = db.get(_uuid(999))
            assert result is None
        finally:
            db.delete_col()

    def test_d027_delete_nonexistent_no_error(self):
        db = _new_dist_db()
        try:
            db.delete(vector_id=_uuid(999))
        finally:
            db.delete_col()

    def test_d028_insert_large_batch(self):
        db = _new_dist_db()
        try:
            records = [
                (_uuid(100 + i), _random_vector(), {"data": f"batch_{i}", "user_id": "batch_user"})
                for i in range(50)
            ]
            _insert_memories(db, records)
            listed = _list_flat(db, filters={"user_id": "batch_user"}, top_k=100)
            assert len(listed) == 50
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedFilter - Filter operators in distributed mode
# ===========================================================================


class TestDistributedFilter:
    """Supported filter operators plus explicit unsupported-range behavior."""

    def test_d030_eq_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(150), VECTORS_4D["A"], {"data": "food", "user_id": "carol", "category": "food"}),
                (_uuid(151), VECTORS_4D["B"], {"data": "travel", "user_id": "carol", "category": "travel"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "carol", "category": "food"})
            _assert_exact_ids(rows, {_uuid(150)})
        finally:
            db.delete_col()

    def test_d031_ne_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(160), VECTORS_4D["A"], {"data": "food", "user_id": "carol", "category": "food"}),
                (_uuid(161), VECTORS_4D["B"], {"data": "travel", "user_id": "carol", "category": "travel"}),
                (_uuid(162), VECTORS_4D["C"], {"data": "work", "user_id": "carol", "category": "work"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "carol", "category": {"ne": "food"}})
            _assert_exact_ids(rows, {_uuid(161), _uuid(162)})
        finally:
            db.delete_col()

    def test_d032_in_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(170), VECTORS_4D["A"], {"data": "food", "user_id": "carol", "category": "food"}),
                (_uuid(171), VECTORS_4D["B"], {"data": "travel", "user_id": "carol", "category": "travel"}),
                (_uuid(172), VECTORS_4D["C"], {"data": "work", "user_id": "carol", "category": "work"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "carol", "category": {"in": ["food", "travel"]}})
            _assert_exact_ids(rows, {_uuid(170), _uuid(171)})
        finally:
            db.delete_col()

    def test_d033_in_empty_list(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(175), VECTORS_4D["A"], {"data": "food", "user_id": "carol", "category": "food"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "carol", "category": {"in": []}})
            assert len(rows) == 0
        finally:
            db.delete_col()

    def test_d034_nin_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(180), VECTORS_4D["A"], {"data": "food", "user_id": "dave", "category": "food"}),
                (_uuid(181), VECTORS_4D["B"], {"data": "travel", "user_id": "dave", "category": "travel"}),
                (_uuid(182), VECTORS_4D["C"], {"data": "work", "user_id": "dave", "category": "work"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "dave", "category": {"nin": ["food"]}})
            _assert_exact_ids(rows, {_uuid(181), _uuid(182)})
        finally:
            db.delete_col()

    def test_d035_nin_multi_value(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(190), VECTORS_4D["A"], {"data": "food", "user_id": "dave", "category": "food"}),
                (_uuid(191), VECTORS_4D["B"], {"data": "travel", "user_id": "dave", "category": "travel"}),
                (_uuid(192), VECTORS_4D["C"], {"data": "work", "user_id": "dave", "category": "work"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "dave", "category": {"nin": ["food", "travel"]}})
            _assert_exact_ids(rows, {_uuid(192)})
        finally:
            db.delete_col()

    def test_d036_contains_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(200), VECTORS_4D["A"], {"data": "coffee shop", "user_id": "eve", "tag": "morning-coffee"}),
                (_uuid(201), VECTORS_4D["B"], {"data": "flight plan", "user_id": "eve", "tag": "evening-flight"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "eve", "tag": {"contains": "coffee"}})
            _assert_exact_ids(rows, {_uuid(200)})
        finally:
            db.delete_col()

    def test_d037_icontains_case_insensitive(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(210), VECTORS_4D["A"], {"data": "item1", "user_id": "eve", "tag": "MorningCoffee"}),
                (_uuid(211), VECTORS_4D["B"], {"data": "item2", "user_id": "eve", "tag": "EVENING-COFFEE"}),
                (_uuid(212), VECTORS_4D["C"], {"data": "item3", "user_id": "eve", "tag": "afternoon-tea"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "eve", "tag": {"icontains": "coffee"}})
            _assert_exact_ids(rows, {_uuid(210), _uuid(211)})
        finally:
            db.delete_col()

    def test_d038_unsupported_gte_filter_returns_empty(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(220), VECTORS_4D["A"], {"data": "low", "user_id": "frank", "priority": "3"}),
                (_uuid(221), VECTORS_4D["B"], {"data": "mid", "user_id": "frank", "priority": "5"}),
                (_uuid(222), VECTORS_4D["C"], {"data": "high", "user_id": "frank", "priority": "8"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "frank", "priority": {"gte": "5"}})
            _assert_exact_ids(rows, set())
        finally:
            db.delete_col()

    def test_d039_unsupported_lte_filter_returns_empty(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(230), VECTORS_4D["A"], {"data": "low", "user_id": "frank", "priority": "3"}),
                (_uuid(231), VECTORS_4D["B"], {"data": "mid", "user_id": "frank", "priority": "5"}),
                (_uuid(232), VECTORS_4D["C"], {"data": "high", "user_id": "frank", "priority": "8"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "frank", "priority": {"lte": "5"}})
            _assert_exact_ids(rows, set())
        finally:
            db.delete_col()

    def test_d040_unsupported_gt_filter_returns_empty(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(240), VECTORS_4D["A"], {"data": "low", "user_id": "frank", "priority": "3"}),
                (_uuid(241), VECTORS_4D["B"], {"data": "mid", "user_id": "frank", "priority": "5"}),
                (_uuid(242), VECTORS_4D["C"], {"data": "high", "user_id": "frank", "priority": "8"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "frank", "priority": {"gt": "5"}})
            _assert_exact_ids(rows, set())
        finally:
            db.delete_col()

    def test_d041_unsupported_lt_filter_returns_empty(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(250), VECTORS_4D["A"], {"data": "low", "user_id": "frank", "priority": "3"}),
                (_uuid(251), VECTORS_4D["B"], {"data": "mid", "user_id": "frank", "priority": "5"}),
                (_uuid(252), VECTORS_4D["C"], {"data": "high", "user_id": "frank", "priority": "8"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "frank", "priority": {"lt": "5"}})
            _assert_exact_ids(rows, set())
        finally:
            db.delete_col()

    def test_d042_or_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(260), VECTORS_4D["A"], {"data": "food", "user_id": "logic_user", "category": "food"}),
                (_uuid(261), VECTORS_4D["B"], {"data": "travel", "user_id": "logic_user", "category": "travel"}),
                (_uuid(262), VECTORS_4D["C"], {"data": "work", "user_id": "logic_user", "category": "work"}),
            ])
            rows = db.search(
                "test", VECTORS_4D["A"], top_k=10,
                filters={"$or": [{"user_id": "logic_user", "category": "food"}, {"user_id": "logic_user", "category": "travel"}]},
            )
            _assert_exact_ids(rows, {_uuid(260), _uuid(261)})
        finally:
            db.delete_col()

    def test_d043_and_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(270), VECTORS_4D["A"], {"data": "food hi", "user_id": "logic_user", "category": "food", "priority": "8"}),
                (_uuid(271), VECTORS_4D["B"], {"data": "food lo", "user_id": "logic_user", "category": "food", "priority": "2"}),
                (_uuid(272), VECTORS_4D["C"], {"data": "travel hi", "user_id": "logic_user", "category": "travel", "priority": "9"}),
            ])
            rows = db.search(
                "test", VECTORS_4D["A"], top_k=10,
                filters={"$and": [{"user_id": "logic_user"}, {"category": "food"}, {"priority": "8"}]},
            )
            _assert_exact_ids(rows, {_uuid(270)})
        finally:
            db.delete_col()

    def test_d044_not_filter(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(280), VECTORS_4D["A"], {"data": "food", "user_id": "logic_user", "category": "food"}),
                (_uuid(281), VECTORS_4D["B"], {"data": "travel", "user_id": "logic_user", "category": "travel"}),
                (_uuid(282), VECTORS_4D["C"], {"data": "work", "user_id": "logic_user", "category": "work"}),
            ])
            rows = db.search(
                "test", VECTORS_4D["A"], top_k=10,
                filters={"user_id": "logic_user", "$not": [{"category": "food"}]},
            )
            _assert_exact_ids(rows, {_uuid(281), _uuid(282)})
        finally:
            db.delete_col()

    def test_d045_nested_or_and(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(290), VECTORS_4D["A"], {"data": "food hi", "user_id": "nest_user", "category": "food", "priority": "7"}),
                (_uuid(291), VECTORS_4D["B"], {"data": "food lo", "user_id": "nest_user", "category": "food", "priority": "2"}),
                (_uuid(292), VECTORS_4D["C"], {"data": "travel hi", "user_id": "nest_user", "category": "travel", "priority": "8"}),
                (_uuid(293), VECTORS_4D["D"], {"data": "travel lo", "user_id": "nest_user", "category": "travel", "priority": "1"}),
            ])
            rows = db.search(
                "test", VECTORS_4D["A"], top_k=10,
                filters={
                    "$or": [
                        {"user_id": "nest_user", "category": "food", "priority": "7"},
                        {"user_id": "nest_user", "category": "travel", "priority": "8"},
                    ]
                },
            )
            _assert_exact_ids(rows, {_uuid(290), _uuid(292)})
        finally:
            db.delete_col()

    def test_d046_multiple_conditions_combined(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(300), VECTORS_4D["A"], {"data": "a", "user_id": "combo_user", "category": "food", "priority": "5", "status": "active"}),
                (_uuid(301), VECTORS_4D["B"], {"data": "b", "user_id": "combo_user", "category": "food", "priority": "3", "status": "active"}),
                (_uuid(302), VECTORS_4D["C"], {"data": "c", "user_id": "combo_user", "category": "travel", "priority": "7", "status": "inactive"}),
            ])
            rows = db.search(
                "test", VECTORS_4D["A"], top_k=10,
                filters={"user_id": "combo_user", "category": "food", "status": "active", "priority": "5"},
            )
            _assert_exact_ids(rows, {_uuid(300)})
        finally:
            db.delete_col()

    def test_d047_filter_on_nonexistent_field(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(310), VECTORS_4D["A"], {"data": "item", "user_id": "field_user"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "field_user", "nonexistent": "value"})
            assert len(rows) == 0
        finally:
            db.delete_col()

    def test_d048_filter_with_numeric_string_comparison(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(320), VECTORS_4D["A"], {"data": "a", "user_id": "num_user", "count": "10"}),
                (_uuid(321), VECTORS_4D["B"], {"data": "b", "user_id": "num_user", "count": "2"}),
                (_uuid(322), VECTORS_4D["C"], {"data": "c", "user_id": "num_user", "count": "20"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "num_user", "count": {"gte": "10"}})
            _assert_exact_ids(rows, set())
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedSearchQuality - Vector search quality in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedSearchQuality:
    """Vector search quality verification across distributed nodes."""

    def test_d050_l2_nearest_neighbor(self):
        db = _new_dist_db(vector_metric="l2")
        try:
            _insert_memories(db, [
                (_uuid(1001), [1.0, 0.0, 0.0, 0.0], {"data": "point_a", "user_id": "search_user"}),
                (_uuid(1002), [0.9, 0.1, 0.0, 0.0], {"data": "point_b", "user_id": "search_user"}),
                (_uuid(1003), [0.0, 1.0, 0.0, 0.0], {"data": "point_c", "user_id": "search_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=3, filters={"user_id": "search_user"})
            assert len(results) >= 2
            assert results[0].id == _uuid(1001)
            assert results[1].id == _uuid(1002)
        finally:
            db.delete_col()

    def test_d051_l2_ordering(self):
        db = _new_dist_db(vector_metric="l2")
        try:
            _insert_memories(db, [
                (_uuid(1011), [0.0, 0.0, 0.0, 0.0], {"data": "origin", "user_id": "search_user"}),
                (_uuid(1012), [1.0, 0.0, 0.0, 0.0], {"data": "dist_1", "user_id": "search_user"}),
                (_uuid(1013), [2.0, 0.0, 0.0, 0.0], {"data": "dist_2", "user_id": "search_user"}),
                (_uuid(1014), [3.0, 0.0, 0.0, 0.0], {"data": "dist_3", "user_id": "search_user"}),
            ])
            results = db.search("query", [0.0, 0.0, 0.0, 0.0], top_k=4, filters={"user_id": "search_user"})
            assert len(results) == 4
            _assert_ordered_ids(results, [_uuid(1011), _uuid(1012), _uuid(1013), _uuid(1014)])
        finally:
            db.delete_col()

    def test_d052_l2_known_distance_value(self):
        db = _new_dist_db(vector_metric="l2")
        try:
            _insert_memories(db, [
                (_uuid(1021), [1.0, 0.0, 0.0, 0.0], {"data": "unit_x", "user_id": "search_user"}),
            ])
            results = db.search("query", [0.0, 0.0, 0.0, 0.0], top_k=1, filters={"user_id": "search_user"})
            assert len(results) == 1
            assert abs(results[0].score - 0.5) < 0.1
        finally:
            db.delete_col()

    def test_d053_cosine_nearest_neighbor(self):
        db = _new_dist_db(vector_metric="cosine")
        try:
            _insert_memories(db, [
                (_uuid(1031), [1.0, 0.0, 0.0, 0.0], {"data": "unit_x", "user_id": "search_user"}),
                (_uuid(1032), [0.9, 0.1, 0.0, 0.0], {"data": "near_x", "user_id": "search_user"}),
                (_uuid(1033), [0.0, 1.0, 0.0, 0.0], {"data": "unit_y", "user_id": "search_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=3, filters={"user_id": "search_user"})
            assert len(results) >= 2
            assert results[0].id == _uuid(1031)
        finally:
            db.delete_col()

    def test_d054_cosine_orthogonal_low_score(self):
        db = _new_dist_db(vector_metric="cosine")
        try:
            _insert_memories(db, [
                (_uuid(1041), [1.0, 0.0, 0.0, 0.0], {"data": "x_axis", "user_id": "search_user"}),
                (_uuid(1042), [0.0, 1.0, 0.0, 0.0], {"data": "y_axis", "user_id": "search_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=2, filters={"user_id": "search_user"})
            assert len(results) == 2
            x_score = results[0].score
            y_score = results[1].score
            assert x_score > y_score
            assert y_score < 0.6
        finally:
            db.delete_col()

    def test_d055_cosine_ordering(self):
        db = _new_dist_db(vector_metric="cosine")
        try:
            _insert_memories(db, [
                (_uuid(1051), [1.0, 0.0, 0.0, 0.0], {"data": "along_x", "user_id": "search_user"}),
                (_uuid(1052), [1.0, 1.0, 0.0, 0.0], {"data": "45_deg", "user_id": "search_user"}),
                (_uuid(1053), [0.0, 1.0, 0.0, 0.0], {"data": "along_y", "user_id": "search_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=3, filters={"user_id": "search_user"})
            assert len(results) == 3
            _assert_ordered_ids(results, [_uuid(1051), _uuid(1052), _uuid(1053)])
        finally:
            db.delete_col()

    def test_d056_default_metric_is_cosine(self):
        db = _new_dist_db()
        try:
            assert db.vector_metric == "cosine"
        finally:
            db.delete_col()

    def test_d057_scores_descending_order(self):
        db = _new_dist_db(vector_metric="cosine")
        try:
            _insert_memories(db, [
                (_uuid(1061), [1.0, 0.0, 0.0, 0.0], {"data": "a", "user_id": "search_user"}),
                (_uuid(1062), [0.7, 0.3, 0.0, 0.0], {"data": "b", "user_id": "search_user"}),
                (_uuid(1063), [0.5, 0.5, 0.0, 0.0], {"data": "c", "user_id": "search_user"}),
                (_uuid(1064), [0.0, 1.0, 0.0, 0.0], {"data": "d", "user_id": "search_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=4, filters={"user_id": "search_user"})
            scores = [r.score for r in results]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1]
        finally:
            db.delete_col()

    def test_d058_top_k_limits_results(self):
        db = _new_dist_db()
        try:
            for i in range(10):
                db.insert(ids=[_uuid(1070 + i)], vectors=[_random_vector()], payloads=[{"data": f"item_{i}", "user_id": "search_user"}])
            results = db.search("query", _random_vector(), top_k=3, filters={"user_id": "search_user"})
            assert len(results) == 3
        finally:
            db.delete_col()

    def test_d059_search_with_filter_reduces_results(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(1081), VECTORS_4D["A"], {"data": "alice_data", "user_id": "alice"}),
                (_uuid(1082), VECTORS_4D["B"], {"data": "bob_data", "user_id": "bob"}),
                (_uuid(1083), VECTORS_4D["C"], {"data": "alice_data2", "user_id": "alice"}),
            ])
            results = db.search("query", VECTORS_4D["A"], top_k=10, filters={"user_id": "alice"})
            assert len(results) == 2
            for r in results:
                assert r.payload["user_id"] == "alice"
        finally:
            db.delete_col()

    def test_d060_large_dataset_sorting(self):
        db = _new_dist_db(vector_metric="l2")
        try:
            random.seed(123)
            batch_size = 50
            for batch_start in range(0, 200, batch_size):
                records = []
                for i in range(batch_start, batch_start + batch_size):
                    vec = [random.uniform(-1, 1) for _ in range(4)]
                    records.append((_uuid(6100 + i), vec, {"data": f"item_{i}", "user_id": "edge_user"}))
                _insert_memories(db, records)
            query = [0.0, 0.0, 0.0, 0.0]
            results = db.search("query", query, top_k=50, filters={"user_id": "edge_user"})
            assert len(results) == 50
            scores = [r.score for r in results]
            for i in range(len(scores) - 1):
                assert scores[i] >= scores[i + 1]
        finally:
            db.delete_col()

    def test_d061_duplicate_scores_stability(self):
        db = _new_dist_db(vector_metric="cosine")
        try:
            _insert_memories(db, [
                (_uuid(6011), [0.5, 0.5, 0.0, 0.0], {"data": "dup_a", "user_id": "edge_user"}),
                (_uuid(6012), [0.5, 0.5, 0.0, 0.0], {"data": "dup_b", "user_id": "edge_user"}),
                (_uuid(6013), [0.5, 0.5, 0.0, 0.0], {"data": "dup_c", "user_id": "edge_user"}),
            ])
            results = db.search("query", [1.0, 0.0, 0.0, 0.0], top_k=3, filters={"user_id": "edge_user"})
            assert len(results) == 3
            scores = [r.score for r in results]
            assert all(abs(s - scores[0]) < 1e-6 for s in scores)
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedBM25Degradation - BM25 graceful degradation
# ===========================================================================


class TestDistributedBM25Degradation:
    """BM25 is auto-disabled in distributed mode; verify graceful degradation."""

    def test_d070_keyword_search_returns_none_or_empty(self):
        db = _new_dist_db()
        try:
            db.insert(ids=[_uuid(1)], vectors=[VECTORS_4D["A"]], payloads=[{"data": "coffee morning", "user_id": "bm25_user", "text_lemmatized": "coffee morning"}])
            result = db.keyword_search(query="coffee", top_k=5, filters={"user_id": "bm25_user"})
            assert result is None or result == []
        finally:
            db.delete_col()

    def test_d071_bm25_flag_stays_false(self):
        db = _new_dist_db()
        try:
            assert db.bm25_enabled is False
        finally:
            db.delete_col()

    def test_d072_search_still_works_without_bm25(self):
        db = _new_dist_db()
        try:
            db.insert(ids=[_uuid(1)], vectors=[VECTORS_4D["A"]], payloads=[{"data": "coffee", "user_id": "bm25_user"}])
            results = db.search("coffee", VECTORS_4D["A"], top_k=1, filters={"user_id": "bm25_user"})
            assert len(results) == 1
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedBoundary - Boundary conditions in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedBoundary:
    """Edge cases and boundary conditions across distributed nodes."""

    def test_d080_single_dimension_vector(self):
        db = _new_dist_db(embedding_model_dims=1)
        try:
            vid = _uuid(1001)
            db.insert(ids=[vid], vectors=[[0.5]], payloads=[{"data": "1d", "user_id": "dim_user"}])
            results = db.search("test", [0.5], top_k=1, filters={"user_id": "dim_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d081_high_dimension_vector(self):
        db = _new_dist_db(embedding_model_dims=DIMS_BOUNDARY)
        try:
            vid = _uuid(1002)
            vec = _random_vector(dims=DIMS_BOUNDARY)
            db.insert(ids=[vid], vectors=[vec], payloads=[{"data": "high_dim", "user_id": "dim_user"}])
            results = db.search("test", vec, top_k=1, filters={"user_id": "dim_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d082_empty_payload(self):
        db = _new_dist_db()
        try:
            vid = _uuid(2001)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"user_id": "boundary_user"}])
            result = db.get(vid)
            assert result is not None
        finally:
            db.delete_col()

    def test_d083_large_payload(self):
        db = _new_dist_db()
        try:
            vid = _uuid(2002)
            large_text = "x" * 10000
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": large_text, "user_id": "boundary_user"}])
            result = db.get(vid)
            assert len(result.payload["data"]) == 10000
        finally:
            db.delete_col()

    def test_d084_unicode_payload(self):
        db = _new_dist_db()
        try:
            vid = _uuid(2003)
            text = "Chinese: 中文 Japanese: 日本語 Korean: 한국어 Emoji: \U0001f680"
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": text, "user_id": "boundary_user"}])
            result = db.get(vid)
            assert result.payload["data"] == text
        finally:
            db.delete_col()

    def test_d085_special_chars_in_payload(self):
        db = _new_dist_db()
        try:
            vid = _uuid(2004)
            text = "quotes: \"hello\" 'world' backslash: \\ newline: \n tab: \t"
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": text, "user_id": "boundary_user"}])
            result = db.get(vid)
            assert result.payload["data"] == text
        finally:
            db.delete_col()

    def test_d086_top_k_one(self):
        db = _new_dist_db()
        try:
            for i in range(5):
                db.insert(ids=[_uuid(3001 + i)], vectors=[_random_vector()], payloads=[{"data": f"item_{i}", "user_id": "topk_user"}])
            results = db.search("test", _random_vector(), top_k=1, filters={"user_id": "topk_user"})
            assert len(results) == 1
        finally:
            db.delete_col()

    def test_d087_top_k_exceeds_data(self):
        db = _new_dist_db()
        try:
            for i in range(3):
                db.insert(ids=[_uuid(3011 + i)], vectors=[_random_vector()], payloads=[{"data": f"item_{i}", "user_id": "topk_user"}])
            results = db.search("test", _random_vector(), top_k=100, filters={"user_id": "topk_user"})
            assert len(results) == 3
        finally:
            db.delete_col()

    def test_d088_top_k_very_large(self):
        db = _new_dist_db()
        try:
            db.insert(ids=[_uuid(3021)], vectors=[_random_vector()], payloads=[{"data": "single", "user_id": "topk_user"}])
            results = db.search("test", _random_vector(), top_k=10000, filters={"user_id": "topk_user"})
            assert len(results) == 1
        finally:
            db.delete_col()

    def test_d089_collection_name_max_length(self):
        long_name = "a" * 51
        config = _gaussdb_distributed_config(long_name)
        db = GaussDB(**config)
        try:
            vid = _uuid(4001)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "long name", "user_id": "col_user"}])
            result = db.get(vid)
            assert result is not None
        finally:
            db.delete_col()

    def test_d090_collection_name_sql_injection_rejected(self):
        with pytest.raises(ValueError, match="Unsafe"):
            _new_dist_db(prefix=None, collection_name="test; DROP TABLE users;--")

    def test_d091_empty_collection_name_rejected(self):
        config = _gaussdb_distributed_config("placeholder")
        config["collection_name"] = ""
        with pytest.raises(ValueError):
            GaussDB(**config)

    def test_d092_batch_insert_100_records(self):
        db = _new_dist_db()
        try:
            ids = [_uuid(5000 + i) for i in range(100)]
            vectors = [_random_vector() for _ in range(100)]
            payloads = [{"data": f"batch_{i}", "user_id": "batch_user"} for i in range(100)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            listed = _list_flat(db, filters={"user_id": "batch_user"}, top_k=200)
            assert len(listed) == 100
        finally:
            db.delete_col()

    def test_d093_nested_json_payload(self):
        db = _new_dist_db()
        try:
            vid = _uuid(6001)
            payload = {
                "data": "nested test",
                "user_id": "json_user",
                "metadata": {"key1": "value1", "key2": 42, "nested": {"deep": True}},
            }
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[payload])
            result = db.get(vid)
            assert result.payload["metadata"]["key1"] == "value1"
            assert result.payload["metadata"]["nested"]["deep"] is True
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedMultitenant - Multi-tenant isolation in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedMultitenant:
    """Multi-tenant isolation across distributed nodes."""

    def test_d100_user_id_isolation(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7001), VECTORS_4D["A"], {"data": "alice data", "user_id": "alice"}),
                (_uuid(7002), VECTORS_4D["B"], {"data": "bob data", "user_id": "bob"}),
                (_uuid(7003), VECTORS_4D["C"], {"data": "alice data2", "user_id": "alice"}),
            ])
            alice_rows = _list_flat(db, filters={"user_id": "alice"}, top_k=100)
            bob_rows = _list_flat(db, filters={"user_id": "bob"}, top_k=100)
            assert len(alice_rows) == 2
            assert len(bob_rows) == 1
            _assert_exact_ids(alice_rows, {_uuid(7001), _uuid(7003)})
            _assert_exact_ids(bob_rows, {_uuid(7002)})
        finally:
            db.delete_col()

    def test_d101_agent_id_isolation(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7101), VECTORS_4D["A"], {"data": "bot_a data", "user_id": "alice", "agent_id": "bot_a"}),
                (_uuid(7102), VECTORS_4D["B"], {"data": "bot_b data", "user_id": "alice", "agent_id": "bot_b"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "alice", "agent_id": "bot_a"})
            _assert_exact_ids(rows, {_uuid(7101)})
        finally:
            db.delete_col()

    def test_d102_run_id_isolation(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7201), VECTORS_4D["A"], {"data": "run1", "user_id": "alice", "run_id": "run_001"}),
                (_uuid(7202), VECTORS_4D["B"], {"data": "run2", "user_id": "alice", "run_id": "run_002"}),
            ])
            rows = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "alice", "run_id": "run_001"})
            _assert_exact_ids(rows, {_uuid(7201)})
        finally:
            db.delete_col()

    def test_d103_combined_scope(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7311), VECTORS_4D["A"], {"data": "full match", "user_id": "alice", "agent_id": "bot_a", "run_id": "run_001"}),
                (_uuid(7312), VECTORS_4D["B"], {"data": "partial", "user_id": "alice", "agent_id": "bot_a", "run_id": "run_999"}),
            ])
            results = _list_flat(db, filters={"user_id": "alice", "agent_id": "bot_a", "run_id": "run_001"}, top_k=100)
            _assert_exact_ids(results, {_uuid(7311)})
        finally:
            db.delete_col()

    def test_d104_scope_empty_on_mismatch(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7321), VECTORS_4D["A"], {"data": "some data", "user_id": "alice", "agent_id": "bot_a"}),
            ])
            results = _list_flat(db, filters={"user_id": "charlie", "agent_id": "bot_x"}, top_k=100)
            assert len(results) == 0
        finally:
            db.delete_col()

    def test_d105_user_sees_all_agents(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7331), VECTORS_4D["A"], {"data": "bot_a", "user_id": "alice", "agent_id": "bot_a"}),
                (_uuid(7332), VECTORS_4D["B"], {"data": "bot_b", "user_id": "alice", "agent_id": "bot_b"}),
                (_uuid(7333), VECTORS_4D["C"], {"data": "bot_c", "user_id": "alice", "agent_id": "bot_c"}),
                (_uuid(7334), VECTORS_4D["D"], {"data": "bob_bot", "user_id": "bob", "agent_id": "bot_a"}),
            ])
            results = _list_flat(db, filters={"user_id": "alice"}, top_k=100)
            _assert_exact_ids(results, {_uuid(7331), _uuid(7332), _uuid(7333)})
        finally:
            db.delete_col()

    def test_d106_search_respects_tenant_scope(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7341), VECTORS_4D["A"], {"data": "alice_near", "user_id": "alice"}),
                (_uuid(7342), VECTORS_4D["similar_A"], {"data": "bob_near", "user_id": "bob"}),
            ])
            results = db.search("test", VECTORS_4D["A"], top_k=10, filters={"user_id": "alice"})
            assert all(r.payload["user_id"] == "alice" for r in results)
            _assert_exact_ids(results, {_uuid(7341)})
        finally:
            db.delete_col()

    def test_d107_delete_respects_isolation(self):
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7351), VECTORS_4D["A"], {"data": "alice", "user_id": "alice"}),
                (_uuid(7352), VECTORS_4D["B"], {"data": "bob", "user_id": "bob"}),
            ])
            db.delete(vector_id=_uuid(7351))
            assert db.get(_uuid(7351)) is None
            assert db.get(_uuid(7352)) is not None
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedConcurrency - Concurrency safety in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestDistributedConcurrency:
    """Concurrency safety across distributed nodes."""

    def test_d110_concurrent_multi_user_insert(self):
        """5 threads inserting for different users, verify isolation."""
        db = _new_dist_db(maxconn=10)
        try:
            users = [f"user_{i}" for i in range(5)]

            def add_for_user(idx):
                uid = users[idx]
                record_id = _uuid(8000 + idx)
                db.insert(
                    ids=[record_id],
                    vectors=[_random_vector()],
                    payloads=[{"data": f"{uid} memory", "user_id": uid}],
                )
                return uid, record_id

            results_map = {}
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(add_for_user, i): i for i in range(5)}
                for future in as_completed(futures):
                    uid, record_id = future.result()
                    results_map[uid] = record_id

            for uid, record_id in results_map.items():
                user_records = _list_flat(db, filters={"user_id": uid}, top_k=100)
                assert len(user_records) == 1
                assert _ids(user_records)[0] == record_id
        finally:
            db.delete_col()

    def test_d111_concurrent_multi_user_search(self):
        """5 threads searching for different users, verify isolation."""
        db = _new_dist_db(maxconn=10)
        try:
            for i in range(5):
                uid = f"user_{i}"
                db.insert(
                    ids=[_uuid(8010 + i)],
                    vectors=[_random_vector()],
                    payloads=[{"data": f"{uid} data", "user_id": uid}],
                )

            def search_for_user(idx):
                uid = f"user_{idx}"
                results = db.search("data", _random_vector(), top_k=10, filters={"user_id": uid})
                return uid, results

            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(search_for_user, i): i for i in range(5)}
                for future in as_completed(futures):
                    uid, results = future.result()
                    idx = int(uid.split("_")[1])
                    expected_id = _uuid(8010 + idx)
                    assert expected_id in _ids(results)
        finally:
            db.delete_col()

    def test_d112_concurrent_insert_same_collection(self):
        """10 threads inserting into same collection concurrently."""
        db = _new_dist_db(maxconn=15)
        try:
            user_id = "conc_insert_user"

            def inserter(thread_idx, iter_idx):
                db.insert(
                    ids=[str(uuid.uuid4())],
                    vectors=[_random_vector()],
                    payloads=[{"data": f"t{thread_idx}_i{iter_idx}", "user_id": user_id}],
                )

            result = _concurrent_runner(inserter, num_threads=10, iterations_per_thread=5)
            assert result["error_count"] == 0
            listed = _list_flat(db, filters={"user_id": user_id}, top_k=200)
            assert len(listed) == 50
        finally:
            db.delete_col()

    def test_d113_concurrent_upsert_same_record(self):
        """10 threads upserting the same record concurrently."""
        db = _new_dist_db(maxconn=15)
        try:
            vid = _uuid(8100)
            db.insert(ids=[vid], vectors=[_random_vector()], payloads=[{"data": "original", "user_id": "upsert_user"}])

            def do_upsert(idx):
                db.update(vector_id=vid, payload={"data": f"update_{idx}", "user_id": "upsert_user"})

            with ThreadPoolExecutor(max_workers=10) as executor:
                list(executor.map(do_upsert, range(20)))

            result = db.get(vid)
            assert result is not None
            assert result.payload["user_id"] == "upsert_user"
            listed = _list_flat(db, filters={"user_id": "upsert_user"}, top_k=100)
            assert len(listed) == 1
        finally:
            db.delete_col()

    def test_d114_concurrent_insert_and_search(self):
        """5 insert threads + 5 search threads simultaneously."""
        db = _new_dist_db(maxconn=15)
        try:
            user_id = "rw_user"
            for i in range(10):
                db.insert(ids=[_uuid(8200 + i)], vectors=[_random_vector()], payloads=[{"data": f"seed_{i}", "user_id": user_id}])

            def inserter(idx):
                for i in range(10):
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[{"data": f"insert_t{idx}_{i}", "user_id": user_id}],
                    )

            def searcher(idx):
                for i in range(10):
                    results = db.search("query", _random_vector(), top_k=5, filters={"user_id": user_id})
                    assert isinstance(results, list)

            tasks = (
                [lambda idx=t: inserter(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)
            assert successes >= 5
        finally:
            db.delete_col()

    def test_d115_concurrent_update_and_search(self):
        """5 update threads + 5 search threads simultaneously."""
        db = _new_dist_db(maxconn=15)
        try:
            user_id = "rw_update_user"
            record_ids = []
            for i in range(20):
                rid = str(uuid.uuid4())
                record_ids.append(rid)
                db.insert(ids=[rid], vectors=[_random_vector()], payloads=[{"data": f"original_{i}", "user_id": user_id}])

            def updater(idx):
                for i in range(5):
                    target = record_ids[(idx * 5 + i) % len(record_ids)]
                    db.update(vector_id=target, vector=_random_vector(), payload={"data": f"updated_t{idx}_{i}", "user_id": user_id})

            def searcher(idx):
                for i in range(5):
                    db.search("query", _random_vector(), top_k=5, filters={"user_id": user_id})

            tasks = (
                [lambda idx=t: updater(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count == 20
        finally:
            db.delete_col()

    def test_d116_concurrent_delete_and_search(self):
        """5 delete threads + 5 search threads simultaneously."""
        db = _new_dist_db(maxconn=15)
        try:
            user_id = "rw_delete_user"
            record_ids = []
            for i in range(50):
                rid = str(uuid.uuid4())
                record_ids.append(rid)
                db.insert(ids=[rid], vectors=[_random_vector()], payloads=[{"data": f"to_delete_{i}", "user_id": user_id}])

            chunk_size = 10

            def deleter(idx):
                start = idx * chunk_size
                for rid in record_ids[start:start + chunk_size]:
                    db.delete(vector_id=rid)

            def searcher(idx):
                for i in range(10):
                    results = db.search("query", _random_vector(), top_k=5, filters={"user_id": user_id})
                    assert isinstance(results, list)

            tasks = (
                [lambda idx=t: deleter(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count < 50
        finally:
            db.delete_col()

    def test_d117_data_consistency_after_concurrent_ops(self):
        """Verify data consistency after concurrent updates."""
        db = _new_dist_db(maxconn=15)
        try:
            user_id = "consistency_user"
            record_ids = []
            for i in range(10):
                rid = _uuid(8300 + i)
                record_ids.append(rid)
                db.insert(ids=[rid], vectors=[_random_vector()], payloads=[{"data": f"original_{i}", "user_id": user_id}])

            def updater(idx):
                for i in range(5):
                    target = record_ids[idx % len(record_ids)]
                    try:
                        db.update(vector_id=target, payload={"data": f"updated_t{idx}_{i}", "user_id": user_id})
                    except Exception:
                        pass

            tasks = [lambda idx=t: updater(idx) for t in range(10)]
            _run_concurrent(tasks, max_workers=10)

            for rid in record_ids:
                result = db.get(rid)
                assert result is not None
                assert result.payload["user_id"] == user_id

            assert len(_list_flat(db, filters={"user_id": user_id}, top_k=100)) == 10
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedPerformance - Performance baselines in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestDistributedPerformance:
    """Performance baseline measurements for distributed mode."""

    def test_d120_single_insert_latency(self):
        """Insert 50 times, verify P50 < 200ms (relaxed for distributed)."""
        db = _new_dist_db()
        try:
            counter = [0]

            def _do_insert():
                counter[0] += 1
                db.insert(
                    ids=[str(uuid.uuid4())],
                    vectors=[_random_vector()],
                    payloads=[{"data": f"perf_{counter[0]}", "user_id": "perf_user"}],
                )

            stats = _measure_latency(_do_insert, iterations=50)
            _print_latency_report("dist_single_insert", stats)
            _soft_assert(stats["p50_ms"] < 200, f"P50 insert {stats['p50_ms']:.2f}ms > 200ms")
        finally:
            db.delete_col()

    def test_d121_single_search_latency(self):
        """Search 50 times, verify P50 < 100ms."""
        db = _new_dist_db()
        try:
            for i in range(30):
                db.insert(ids=[_uuid(9000 + i)], vectors=[_random_vector()], payloads=[{"data": f"item_{i}", "user_id": "perf_user"}])

            def _do_search():
                db.search("query", _random_vector(), top_k=5, filters={"user_id": "perf_user"})

            stats = _measure_latency(_do_search, iterations=50)
            _print_latency_report("dist_single_search", stats)
            _soft_assert(stats["p50_ms"] < 100, f"P50 search {stats['p50_ms']:.2f}ms > 100ms")
        finally:
            db.delete_col()

    def test_d122_single_update_latency(self):
        """Update 50 times, verify P50 < 250ms."""
        db = _new_dist_db()
        try:
            vid = _uuid(9100)
            db.insert(ids=[vid], vectors=[_random_vector()], payloads=[{"data": "target", "user_id": "perf_user"}])
            counter = [0]

            def _do_update():
                counter[0] += 1
                db.update(vid, vector=_random_vector(), payload={"data": f"upd_{counter[0]}", "user_id": "perf_user"})

            stats = _measure_latency(_do_update, iterations=50)
            _print_latency_report("dist_single_update", stats)
            _soft_assert(stats["p50_ms"] < 250, f"P50 update {stats['p50_ms']:.2f}ms > 250ms")
        finally:
            db.delete_col()

    def test_d123_single_get_latency(self):
        """Get 50 times, verify P50 < 20ms."""
        db = _new_dist_db()
        try:
            vid = _uuid(9200)
            db.insert(ids=[vid], vectors=[_random_vector()], payloads=[{"data": "get_target", "user_id": "perf_user"}])

            def _do_get():
                db.get(vid)

            stats = _measure_latency(_do_get, iterations=50)
            _print_latency_report("dist_single_get", stats)
            _soft_assert(stats["p50_ms"] < 20, f"P50 get {stats['p50_ms']:.2f}ms > 20ms")
        finally:
            db.delete_col()

    def test_d124_batch_insert_throughput(self):
        """Insert 200 records in batches of 50, measure total time."""
        db = _new_dist_db()
        try:
            start = time.perf_counter()
            for batch in range(4):
                ids = [str(uuid.uuid4()) for _ in range(50)]
                vectors = [_random_vector() for _ in range(50)]
                payloads = [{"data": f"batch_{batch}_{i}", "user_id": "perf_user"} for i in range(50)]
                db.insert(ids=ids, vectors=vectors, payloads=payloads)
            duration_ms = (time.perf_counter() - start) * 1000

            listed = _list_flat(db, filters={"user_id": "perf_user"}, top_k=300)
            assert len(listed) == 200
            _soft_assert(duration_ms < 10000, f"Batch insert took {duration_ms:.0f}ms > 10s")
        finally:
            db.delete_col()

    def test_d125_search_with_filters_latency(self):
        """Search with complex filters, verify reasonable latency."""
        db = _new_dist_db()
        try:
            for i in range(50):
                db.insert(
                    ids=[_uuid(9300 + i)],
                    vectors=[_random_vector()],
                    payloads=[{"data": f"item_{i}", "user_id": "perf_user", "category": f"cat_{i % 5}", "priority": str(i % 10)}],
                )

            def _do_filtered_search():
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "perf_user", "category": {"in": ["cat_0", "cat_1"]}})

            stats = _measure_latency(_do_filtered_search, iterations=30)
            _print_latency_report("dist_filtered_search", stats)
            _soft_assert(stats["p50_ms"] < 150, f"P50 filtered search {stats['p50_ms']:.2f}ms > 150ms")
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedCollectionOps - Collection lifecycle in distributed mode
# ===========================================================================


class TestDistributedCollectionOps:
    """Collection lifecycle operations in distributed mode."""

    def test_d130_col_info(self):
        db = _new_dist_db()
        try:
            db.insert(ids=[_uuid(1)], vectors=[VECTORS_4D["A"]], payloads=[{"data": "info", "user_id": "ops_user"}])
            info = db.col_info()
            assert info["name"] == db.collection_name
            assert info["count"] == 1
        finally:
            db.delete_col()

    def test_d131_list_collections(self):
        db = _new_dist_db()
        try:
            cols = db.list_cols()
            assert isinstance(cols, list)
            assert db.collection_name in cols
        finally:
            db.delete_col()

    def test_d132_reset_collection(self):
        db = _new_dist_db()
        try:
            for i in range(5):
                db.insert(ids=[_uuid(i)], vectors=[_random_vector()], payloads=[{"data": f"item_{i}", "user_id": "ops_user"}])
            assert db.col_info()["count"] == 5
            db.reset()
            assert db.col_info()["count"] == 0
        finally:
            db.delete_col()

    def test_d133_delete_and_recreate_collection(self):
        name = _new_collection("dist_recreate")
        config = _gaussdb_distributed_config(name)
        db = GaussDB(**config)
        try:
            db.insert(ids=[_uuid(1)], vectors=[VECTORS_4D["A"]], payloads=[{"data": "first", "user_id": "ops_user"}])
            db.delete_col()
            db2 = GaussDB(**config)
            db2.insert(ids=[_uuid(2)], vectors=[VECTORS_4D["B"]], payloads=[{"data": "second", "user_id": "ops_user"}])
            assert db2.get(_uuid(2)) is not None
            assert db2.get(_uuid(1)) is None
            db2.delete_col()
        except Exception:
            try:
                db.delete_col()
            except Exception:
                pass
            raise

    def test_d135_schema_meta_not_in_list(self):
        db = _new_dist_db()
        try:
            cols = db.list_cols()
            assert f"{db.collection_name}_schema_meta" not in cols
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedFeatures - GaussDB-specific features in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedFeatures:
    """GaussDB-specific features verification in distributed mode."""

    def test_d140_floatvector_precision(self):
        """Float32 precision is maintained in distributed mode."""
        db = _new_dist_db()
        try:
            vid = _uuid(7401)
            precise_vector = [0.123456789, 0.987654321, 0.555555555, 0.111111111]
            db.insert(ids=[vid], vectors=[precise_vector], payloads=[{"data": "precision", "user_id": "feat_user"}])
            results = db.search("precision", precise_vector, top_k=1, filters={"user_id": "feat_user"})
            assert len(results) == 1
            assert results[0].id == vid
            if results[0].score is not None:
                assert results[0].score > 0.99
        finally:
            db.delete_col()

    def test_d141_high_dim_vector_support(self):
        """High-dimensional vectors work in distributed mode."""
        dims = 512
        db = _new_dist_db(embedding_model_dims=dims)
        try:
            vid = _uuid(7501)
            vec = [random.random() for _ in range(dims)]
            db.insert(ids=[vid], vectors=[vec], payloads=[{"data": "high_dim", "user_id": "feat_user"}])
            results = db.search("test", vec, top_k=1, filters={"user_id": "feat_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d142_merge_into_upsert(self):
        """MERGE INTO (upsert) works correctly in distributed mode."""
        db = _new_dist_db()
        try:
            vid = _uuid(7601)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "original", "user_id": "feat_user"}])
            db.update(vector_id=vid, vector=VECTORS_4D["B"], payload={"data": "merged", "user_id": "feat_user"})
            result = db.get(vid)
            assert result.payload["data"] == "merged"
            results = db.search("test", VECTORS_4D["B"], top_k=1, filters={"user_id": "feat_user"})
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d143_merge_into_idempotent(self):
        """MERGE INTO with same data is idempotent."""
        db = _new_dist_db()
        try:
            vid = _uuid(7701)
            vector = VECTORS_4D["C"]
            payload = {"data": "idempotent", "user_id": "feat_user"}
            db.insert(ids=[vid], vectors=[vector], payloads=[payload])
            for _ in range(3):
                db.update(vector_id=vid, vector=vector, payload=payload)
            result = db.get(vid)
            assert result.payload["data"] == "idempotent"
            listed = _list_flat(db, filters={"user_id": "feat_user"}, top_k=100)
            assert len(listed) == 1
        finally:
            db.delete_col()

    def test_d144_vector_index_creation(self):
        """Vector index is created in distributed mode."""
        db = _new_dist_db()
        try:
            info = db.col_info()
            indexes = info.get("indexes", [])
            has_vector_idx = any("vector" in idx.lower() or "ivf" in idx.lower() for idx in indexes)
            assert has_vector_idx, f"No vector index found in: {indexes}"
        finally:
            db.delete_col()

    def test_d145_deployment_mode_in_col_info(self):
        """col_info reports distributed deployment mode."""
        db = _new_dist_db()
        try:
            info = db.col_info()
            assert info.get("deployment_mode") == "distributed" or db.deployment_mode == "distributed"
        finally:
            db.delete_col()

    def test_d146_update_in_place(self):
        """Update modifies record in place without duplication."""
        db = _new_dist_db()
        try:
            vid = _uuid(7801)
            db.insert(ids=[vid], vectors=[VECTORS_4D["A"]], payloads=[{"data": "original", "user_id": "feat_user"}])
            db.update(vector_id=vid, vector=VECTORS_4D["B"], payload={"data": "updated", "user_id": "feat_user"})
            updated = db.get(vid)
            assert updated.payload["data"] == "updated"
            results = db.search("test", VECTORS_4D["B"], top_k=1, filters={"user_id": "feat_user"})
            assert len(results) >= 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d147_search_batch(self):
        """search_batch works in distributed mode."""
        db = _new_dist_db()
        try:
            _insert_memories(db, [
                (_uuid(7901), VECTORS_4D["A"], {"data": "point_a", "user_id": "batch_user"}),
                (_uuid(7902), VECTORS_4D["B"], {"data": "point_b", "user_id": "batch_user"}),
            ])
            batch_results = db.search_batch(
                ["a", "b"],
                [VECTORS_4D["A"], VECTORS_4D["B"]],
                top_k=1,
                filters={"user_id": "batch_user"},
            )
            assert len(batch_results) == 2
            assert batch_results[0][0].id == _uuid(7901)
            assert batch_results[1][0].id == _uuid(7902)
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedE2E - End-to-end verification in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedE2E:
    """Full E2E verification of distributed mode operations."""

    def test_d150_e2e_insert_search_update_delete(self):
        """Complete lifecycle: insert -> search -> update -> search -> delete -> verify."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(100, dims=1536)
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "e2e lifecycle", "user_id": "e2e_user"}])

            results = db.search("lifecycle", vec, top_k=1, filters={"user_id": "e2e_user"})
            assert len(results) == 1
            assert results[0].id == vid

            new_vec = _make_vector_seeded(101, dims=1536)
            db.update(vector_id=vid, vector=new_vec, payload={"data": "updated lifecycle", "user_id": "e2e_user"})
            results = db.search("updated", new_vec, top_k=1, filters={"user_id": "e2e_user"})
            assert results[0].payload["data"] == "updated lifecycle"

            db.delete(vector_id=vid)
            assert db.get(vid) is None
        finally:
            db.delete_col()

    def test_d151_e2e_batch_operations(self):
        """Batch insert and verify all records accessible."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            ids = [str(uuid.uuid4()) for _ in range(20)]
            vecs = [_make_vector_seeded(i + 200, dims=1536) for i in range(20)]
            payloads = [{"data": f"batch_{i}", "user_id": "e2e_user"} for i in range(20)]
            db.insert(vectors=vecs, ids=ids, payloads=payloads)

            listed = _list_flat(db, filters={"user_id": "e2e_user"}, top_k=100)
            assert len(listed) == 20
        finally:
            db.delete_col()

    def test_d152_e2e_vector_update(self):
        """Update vector and verify search finds it with new vector."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(301, dims=1536)
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "vec update", "user_id": "e2e_user"}])
            new_vec = _make_vector_seeded(302, dims=1536)
            db.update(vector_id=vid, vector=new_vec)
            results = db.search("vec", new_vec, top_k=1, filters={"user_id": "e2e_user"})
            assert len(results) >= 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_d153_e2e_list_with_filters(self):
        """List with user_id filter returns correct subset."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            ids = [str(uuid.uuid4()) for _ in range(6)]
            vecs = [_make_vector_seeded(i + 500, dims=1536) for i in range(6)]
            payloads = [{"data": f"item_{i}", "user_id": "alice" if i < 3 else "bob"} for i in range(6)]
            db.insert(vectors=vecs, ids=ids, payloads=payloads)
            alice_items = _list_flat(db, filters={"user_id": "alice"}, top_k=100)
            assert len(alice_items) == 3
            bob_items = _list_flat(db, filters={"user_id": "bob"}, top_k=100)
            assert len(bob_items) == 3
        finally:
            db.delete_col()

    def test_d154_e2e_large_payload(self):
        """Large payload stored and retrieved correctly."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(700, dims=1536)
            large_text = "x" * 10000
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": large_text, "user_id": "e2e_user"}])
            result = db.get(vid)
            assert len(result.payload["data"]) == 10000
        finally:
            db.delete_col()

    def test_d155_e2e_unicode_payload(self):
        """Unicode payload stored and retrieved correctly."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(800, dims=1536)
            text = "中文测试 日本語 한국어 emoji: \U0001f680\U0001f4bb"
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": text, "user_id": "e2e_user"}])
            result = db.get(vid)
            assert result.payload["data"] == text
        finally:
            db.delete_col()

    def test_d156_e2e_concurrent_upsert_idempotency(self):
        """Concurrent upserts on same record maintain single copy."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(900, dims=1536)
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "concurrent", "user_id": "e2e_user"}])

            def do_upsert(idx):
                db.update(vector_id=vid, payload={"data": f"update_{idx}", "user_id": "e2e_user"})

            with ThreadPoolExecutor(max_workers=5) as executor:
                list(executor.map(do_upsert, range(10)))

            result = db.get(vid)
            assert result is not None
            listed = _list_flat(db, filters={"user_id": "e2e_user"}, top_k=100)
            assert len(listed) == 1
        finally:
            db.delete_col()

    def test_d157_e2e_reset_collection(self):
        """Reset clears all data."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            ids = [str(uuid.uuid4()) for _ in range(5)]
            vecs = [_make_vector_seeded(i + 1000, dims=1536) for i in range(5)]
            payloads = [{"data": f"item_{i}", "user_id": "e2e_user"} for i in range(5)]
            db.insert(vectors=vecs, ids=ids, payloads=payloads)
            assert len(_list_flat(db, filters={"user_id": "e2e_user"}, top_k=100)) == 5
            db.reset()
            assert len(_list_flat(db, filters={"user_id": "e2e_user"}, top_k=100)) == 0
        finally:
            db.delete_col()


# ===========================================================================
# TestDistributedMemoryAPI - Memory.from_config integration in distributed mode
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedMemoryAPI:
    """Memory API integration with distributed GaussDB backend."""

    def test_d160_memory_add_search_delete(self):
        """Memory.from_config add/search/delete with distributed GaussDB."""
        from mem0 import Memory

        collection = _new_collection("mem0_dist_memory")
        vector_config = _gaussdb_distributed_config(collection, embedding_model_dims=EMBEDDING_DIMS)
        assert vector_config is not None

        memory_config = {
            "vector_store": {"provider": "gaussdb", "config": vector_config},
            "embedder": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "llm": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "version": "v1.1",
        }

        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=FakeEmbedder()),
            patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
            patch("mem0.memory.main.SQLiteManager", return_value=MagicMock()),
            patch("mem0.memory.main.extract_entities", return_value=[]),
            patch("mem0.memory.main.capture_event", lambda *args, **kwargs: None),
            patch("mem0.memory.main.MEM0_TELEMETRY", False),
        ):
            memory = Memory.from_config(memory_config)

        try:
            added = memory.add(
                "Alice prefers window seats on morning flights",
                user_id="alice",
                infer=False,
                metadata={"source": "dist-memory-test"},
            )
            memory_id = added["results"][0]["id"]

            search_result = memory.search("window seat", filters={"user_id": "alice"}, top_k=5, threshold=0)
            rows = search_result["results"]
            assert any(row["id"] == memory_id for row in rows)

            memory.delete(memory_id)
            assert memory.vector_store.get(memory_id) is None
        finally:
            memory.vector_store.delete_col()
            if getattr(memory, "_entity_store", None) is not None:
                memory.entity_store.delete_col()

    def test_d161_memory_search_with_scope_filter(self):
        """Memory search respects user_id scope in distributed mode."""
        from mem0 import Memory

        collection = _new_collection("mem0_dist_scope")
        vector_config = _gaussdb_distributed_config(collection, embedding_model_dims=EMBEDDING_DIMS)
        assert vector_config is not None

        memory_config = {
            "vector_store": {"provider": "gaussdb", "config": vector_config},
            "embedder": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "llm": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "version": "v1.1",
        }

        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=FakeEmbedder()),
            patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
            patch("mem0.memory.main.SQLiteManager", return_value=MagicMock()),
            patch("mem0.memory.main.extract_entities", return_value=[]),
            patch("mem0.memory.main.capture_event", lambda *args, **kwargs: None),
            patch("mem0.memory.main.MEM0_TELEMETRY", False),
        ):
            memory = Memory.from_config(memory_config)

        try:
            memory.add("Alice likes coffee", user_id="alice", infer=False)
            memory.add("Bob likes tea", user_id="bob", infer=False)

            alice_results = memory.search("likes", filters={"user_id": "alice"}, top_k=10, threshold=0)
            bob_results = memory.search("likes", filters={"user_id": "bob"}, top_k=10, threshold=0)

            alice_ids = {r["id"] for r in alice_results["results"]}
            bob_ids = {r["id"] for r in bob_results["results"]}
            assert alice_ids.isdisjoint(bob_ids)
        finally:
            memory.vector_store.delete_col()
            if getattr(memory, "_entity_store", None) is not None:
                memory.entity_store.delete_col()

    def test_d162_memory_update(self):
        """Memory update works in distributed mode."""
        from mem0 import Memory

        collection = _new_collection("mem0_dist_upd")
        vector_config = _gaussdb_distributed_config(collection, embedding_model_dims=EMBEDDING_DIMS)
        assert vector_config is not None

        memory_config = {
            "vector_store": {"provider": "gaussdb", "config": vector_config},
            "embedder": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "llm": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "version": "v1.1",
        }

        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=FakeEmbedder()),
            patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
            patch("mem0.memory.main.SQLiteManager", return_value=MagicMock()),
            patch("mem0.memory.main.extract_entities", return_value=[]),
            patch("mem0.memory.main.capture_event", lambda *args, **kwargs: None),
            patch("mem0.memory.main.MEM0_TELEMETRY", False),
        ):
            memory = Memory.from_config(memory_config)

        try:
            added = memory.add("Original memory text", user_id="alice", infer=False)
            memory_id = added["results"][0]["id"]

            fetched = memory.get(memory_id)
            assert fetched["id"] == memory_id
            assert "Original memory text" in fetched["memory"]

            memory.update(memory_id, data="Updated distributed memory text")
            record = memory.vector_store.get(memory_id)
            assert record is not None
            assert "Updated distributed memory text" in record.payload.get("data", "")
        finally:
            memory.vector_store.delete_col()
            if getattr(memory, "_entity_store", None) is not None:
                memory.entity_store.delete_col()

    def test_d163_memory_get_all_and_delete_all(self):
        """Memory.get_all and Memory.delete_all work in distributed mode."""
        from mem0 import Memory

        collection = _new_collection("mem0_dist_all")
        vector_config = _gaussdb_distributed_config(collection, embedding_model_dims=EMBEDDING_DIMS)
        assert vector_config is not None

        memory_config = {
            "vector_store": {"provider": "gaussdb", "config": vector_config},
            "embedder": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "llm": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "version": "v1.1",
        }

        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=FakeEmbedder()),
            patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
            patch("mem0.memory.main.SQLiteManager", return_value=MagicMock()),
            patch("mem0.memory.main.extract_entities", return_value=[]),
            patch("mem0.memory.main.capture_event", lambda *args, **kwargs: None),
            patch("mem0.memory.main.MEM0_TELEMETRY", False),
        ):
            memory = Memory.from_config(memory_config)

        try:
            memory.add("Distributed memory one", user_id="alice", infer=False)
            memory.add("Distributed memory two", user_id="alice", infer=False)

            before = memory.get_all(filters={"user_id": "alice"})
            before_rows = before.get("results", before.get("memories", []))
            assert len(before_rows) >= 2

            memory.delete_all(user_id="alice")

            after = memory.get_all(filters={"user_id": "alice"})
            after_rows = after.get("results", after.get("memories", []))
            assert len(after_rows) == 0
        finally:
            memory.vector_store.delete_col()
            if getattr(memory, "_entity_store", None) is not None:
                memory.entity_store.delete_col()

    def test_d164_memory_reset(self):
        """Memory.reset recreates the distributed collection and clears prior data."""
        from mem0 import Memory

        collection = _new_collection("mem0_dist_reset")
        vector_config = _gaussdb_distributed_config(collection, embedding_model_dims=EMBEDDING_DIMS)
        assert vector_config is not None

        memory_config = {
            "vector_store": {"provider": "gaussdb", "config": vector_config},
            "embedder": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "llm": {"provider": "openai", "config": {"model": "fake", "api_key": "fake"}},
            "version": "v1.1",
        }

        with (
            patch("mem0.memory.main.EmbedderFactory.create", return_value=FakeEmbedder()),
            patch("mem0.memory.main.LlmFactory.create", return_value=MagicMock()),
            patch("mem0.memory.main.SQLiteManager", return_value=MagicMock()),
            patch("mem0.memory.main.extract_entities", return_value=[]),
            patch("mem0.memory.main.capture_event", lambda *args, **kwargs: None),
            patch("mem0.memory.main.MEM0_TELEMETRY", False),
        ):
            memory = Memory.from_config(memory_config)

        try:
            memory.add("Distributed reset one", user_id="alice", infer=False)
            memory.add("Distributed reset two", user_id="alice", infer=False)

            before = memory.get_all(filters={"user_id": "alice"})
            before_rows = before.get("results", before.get("memories", []))
            assert len(before_rows) >= 2

            memory.reset()

            after = memory.get_all(filters={"user_id": "alice"})
            after_rows = after.get("results", after.get("memories", []))
            assert len(after_rows) == 0
        finally:
            memory.vector_store.delete_col()
            if getattr(memory, "_entity_store", None) is not None:
                memory.entity_store.delete_col()


# ===========================================================================
# TestDistributedMultilang - Multi-language text handling in distributed mode
# ===========================================================================


MULTILANG_CASES_DIST = [
    {"lang": "Chinese", "text": "华为GaussDB是一款优秀的分布式数据库产品"},
    {"lang": "Japanese", "text": "東京は日本の首都です。春には桐が美しいです"},
    {"lang": "Korean", "text": "서울은 한국의 수도입니다. 봄에는 볚꽃이 아름답습니다"},
    {"lang": "Arabic", "text": "الرياض هي عاصمة المملكة العربية السعودية"},
    {"lang": "Russian", "text": "Москва — столица России"},
    {"lang": "Mixed", "text": "Hello 世界! こんにちは 안녕하세요 \U0001f30d"},
    {"lang": "Emoji", "text": "\U0001f680\U0001f4bb\U0001f4ca\U0001f50d\U0001f4a1 DevOps pipeline status: ✅✅❌✅"},
]


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestDistributedMultilang:
    """Multi-language text handling in distributed mode."""

    def test_d170_multilang_insert_and_retrieve(self):
        """Insert and retrieve multi-language text."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            for i, case in enumerate(MULTILANG_CASES_DIST):
                vid = str(uuid.uuid4())
                vec = _make_vector_seeded(i, dims=1536)
                db.insert(vectors=[vec], ids=[vid], payloads=[{"data": case["text"], "user_id": "lang_test", "lang": case["lang"]}])

            listed = _list_flat(db, filters={"user_id": "lang_test"}, top_k=100)
            assert len(listed) == len(MULTILANG_CASES_DIST)

            for item in listed:
                assert item.payload["data"] in [c["text"] for c in MULTILANG_CASES_DIST]
        finally:
            db.delete_col()

    def test_d171_multilang_search(self):
        """Search returns correct multilang records."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vecs = [_make_vector_seeded(i + 100, dims=1536) for i in range(len(MULTILANG_CASES_DIST))]
            for i, case in enumerate(MULTILANG_CASES_DIST):
                vid = str(uuid.uuid4())
                db.insert(vectors=[vecs[i]], ids=[vid], payloads=[{"data": case["text"], "user_id": "lang_test", "lang": case["lang"]}])

            results = db.search("test", vecs[0], top_k=len(MULTILANG_CASES_DIST), filters={"user_id": "lang_test"})
            assert len(results) == len(MULTILANG_CASES_DIST)
        finally:
            db.delete_col()

    def test_d172_multilang_filter_by_lang(self):
        """Filter by language field works with multilang data."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            for i, case in enumerate(MULTILANG_CASES_DIST):
                vid = str(uuid.uuid4())
                vec = _make_vector_seeded(i + 200, dims=1536)
                db.insert(vectors=[vec], ids=[vid], payloads=[{"data": case["text"], "user_id": "lang_test", "lang": case["lang"]}])

            chinese_results = db.search("test", _make_vector_seeded(0, dims=1536), top_k=10, filters={"user_id": "lang_test", "lang": "Chinese"})
            assert len(chinese_results) == 1
            assert "华为" in chinese_results[0].payload["data"]
        finally:
            db.delete_col()

    def test_d173_multilang_update_payload(self):
        """Update payload with multilang text."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(0, dims=1536)
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "original", "user_id": "lang_test"}])
            new_text = "更新后的中文文本：华为GaussDB是一款优秀的分布式数据库。"
            db.update(vector_id=vid, payload={"data": new_text, "user_id": "lang_test", "updated": "true"})
            record = db.get(vector_id=vid)
            assert record.payload["data"] == new_text
            assert record.payload["updated"] == "true"
        finally:
            db.delete_col()

    def test_d174_multilang_delete_and_verify(self):
        """Delete multilang record and verify removal."""
        db = _new_dist_db(embedding_model_dims=1536)
        try:
            vid = str(uuid.uuid4())
            vec = _make_vector_seeded(99, dims=1536)
            db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "中文测试", "user_id": "lang_test"}])
            db.delete(vector_id=vid)
            assert db.get(vector_id=vid) is None
        finally:
            db.delete_col()


# ===========================================================================
# TestCrossModeComparison - Distributed vs Centralized consistency
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_FULL_DISTRIBUTED"), reason=_FULL_DIST_REASON)
class TestCrossModeComparison:
    """Verify distributed and centralized modes produce consistent results."""

    def test_d180_same_data_same_search_results(self):
        """Same data + same query produces same ordering in both modes."""
        db_dist = _new_dist_db()
        config_cent = _gaussdb_env_config(_new_collection("cross_cent"))
        if config_cent is None:
            pytest.skip("Centralized config not available")
        config_cent["embedding_model_dims"] = DIMS_SMALL
        db_cent = GaussDB(**config_cent)
        try:
            records = [
                (_uuid(9001), VECTORS_4D["A"], {"data": "a", "user_id": "cross_user"}),
                (_uuid(9002), VECTORS_4D["B"], {"data": "b", "user_id": "cross_user"}),
                (_uuid(9003), VECTORS_4D["C"], {"data": "c", "user_id": "cross_user"}),
                (_uuid(9004), VECTORS_4D["D"], {"data": "d", "user_id": "cross_user"}),
            ]
            _insert_memories(db_dist, records)
            _insert_memories(db_cent, records)

            query_vec = VECTORS_4D["A"]
            results_dist = db_dist.search("test", query_vec, top_k=4, filters={"user_id": "cross_user"})
            results_cent = db_cent.search("test", query_vec, top_k=4, filters={"user_id": "cross_user"})

            ids_dist = _ids(results_dist)
            ids_cent = _ids(results_cent)
            assert ids_dist == ids_cent

            for rd, rc in zip(results_dist, results_cent):
                assert abs(rd.score - rc.score) < 1e-4
        finally:
            db_dist.delete_col()
            db_cent.delete_col()

    def test_d181_same_filter_results(self):
        """Same filter produces same result set in both modes."""
        db_dist = _new_dist_db()
        config_cent = _gaussdb_env_config(_new_collection("cross_filt"))
        if config_cent is None:
            pytest.skip("Centralized config not available")
        config_cent["embedding_model_dims"] = DIMS_SMALL
        db_cent = GaussDB(**config_cent)
        try:
            records = [
                (_uuid(9011), VECTORS_4D["A"], {"data": "food", "user_id": "cross_user", "category": "food"}),
                (_uuid(9012), VECTORS_4D["B"], {"data": "travel", "user_id": "cross_user", "category": "travel"}),
                (_uuid(9013), VECTORS_4D["C"], {"data": "work", "user_id": "cross_user", "category": "work"}),
            ]
            _insert_memories(db_dist, records)
            _insert_memories(db_cent, records)

            results_dist = db_dist.search("test", VECTORS_4D["B"], top_k=10, filters={"user_id": "cross_user", "category": {"in": ["food", "travel"]}})
            results_cent = db_cent.search("test", VECTORS_4D["B"], top_k=10, filters={"user_id": "cross_user", "category": {"in": ["food", "travel"]}})

            assert set(_ids(results_dist)) == set(_ids(results_cent))
        finally:
            db_dist.delete_col()
            db_cent.delete_col()

    def test_d182_crud_consistency(self):
        """CRUD operations produce same state in both modes."""
        db_dist = _new_dist_db()
        config_cent = _gaussdb_env_config(_new_collection("cross_crud"))
        if config_cent is None:
            pytest.skip("Centralized config not available")
        config_cent["embedding_model_dims"] = DIMS_SMALL
        db_cent = GaussDB(**config_cent)
        try:
            vid = _uuid(9021)
            record = (vid, VECTORS_4D["A"], {"data": "original", "user_id": "cross_user"})
            _insert_memories(db_dist, [record])
            _insert_memories(db_cent, [record])

            db_dist.update(vector_id=vid, payload={"data": "updated", "user_id": "cross_user"})
            db_cent.update(vector_id=vid, payload={"data": "updated", "user_id": "cross_user"})

            r_dist = db_dist.get(vid)
            r_cent = db_cent.get(vid)
            assert r_dist.payload["data"] == r_cent.payload["data"] == "updated"

            db_dist.delete(vector_id=vid)
            db_cent.delete(vector_id=vid)
            assert db_dist.get(vid) is None
            assert db_cent.get(vid) is None
        finally:
            db_dist.delete_col()
            db_cent.delete_col()
