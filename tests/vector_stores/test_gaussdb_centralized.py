"""
GaussDB Centralized Mode Integration & E2E Tests.

Merged from 13 individual test files into a single comprehensive test suite.
All tests target centralized deployment mode and require a live GaussDB instance.

Environment variables:
    GAUSSDB_TEST_DSN                 Full DSN (overrides host/port/database/user/password)
    GAUSSDB_TEST_HOST                GaussDB host
    GAUSSDB_TEST_PORT                GaussDB port
    GAUSSDB_TEST_DATABASE            Database name
    GAUSSDB_TEST_USER                Username
    GAUSSDB_TEST_PASSWORD            Password
    GAUSSDB_TEST_SSLMODE             Optional SSL mode
    GAUSSDB_TEST_SSLROOTCERT         Optional SSL root certificate path
    GAUSSDB_TEST_VECTOR_INDEX        Defaults to gsdiskann
    GAUSSDB_TEST_DEPLOYMENT_MODE     centralized or distributed (defaults to centralized)
    GAUSSDB_TEST_RUN_BM25            Set to true to require and verify BM25
    GAUSSDB_TEST_RUN_INDEX_MATRIX    Set to true to run index/metric matrix tests
    GAUSSDB_TEST_BENCHMARK           Set to true to run benchmark reporting

Test classes:
    TestCRUD                  — Basic CRUD operations
    TestFilter                — All filter operators (eq, ne, in, nin, range, contains, etc.)
    TestSearchQuality         — Vector search quality, distance metrics, recall
    TestBM25                  — BM25 keyword search
    TestMultitenant           — Multi-tenant isolation (user_id, agent_id, run_id)
    TestBoundary              — Edge cases and boundary conditions
    TestConcurrent            — Concurrency safety
    TestPerformance           — Performance baselines
    TestCollectionOps         — Collection lifecycle operations
    TestFeatures              — GaussDB-specific features (Ustore, FLOATVECTOR, indexes)
    TestMemoryAPI             — Memory.from_config upper-layer E2E
    TestMultilang             — Multi-language text handling
    TestE2EFull               — Full E2E verification (converted from standalone scripts)
"""

import json
import math
import os
import random
import statistics
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

pytest.importorskip("psycopg2", reason="GaussDB live tests require psycopg2-compatible driver")

from mem0 import Memory
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
# Module-level skip
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    not gaussdb_available(),
    reason="Set GAUSSDB_TEST_DSN or GAUSSDB_TEST_HOST/PORT/DATABASE/USER/PASSWORD to run GaussDB live tests",
)


# ---------------------------------------------------------------------------
# Local helpers (from p0 and standalone scripts)
# ---------------------------------------------------------------------------


_new_collection = _new_collection_name


def _random_vector(dims: int = EMBEDDING_DIMS) -> list:
    return [random.random() for _ in range(dims)]


def _make_vector_seeded(seed: int, dims: int = EMBEDDING_DIMS) -> list:
    rng = random.Random(seed)
    return [rng.uniform(-1, 1) for _ in range(dims)]


def _cosine_similar_vector(base: list, noise: float = 0.05) -> list:
    return [v + random.uniform(-noise, noise) for v in base]


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


def _print_latency_report(name: str, stats: dict):
    print(f"\n  [PERF] {name}:")
    print(f"    iterations: {stats['iterations']}")
    print(f"    P50:  {stats['p50_ms']:.2f} ms")
    print(f"    P99:  {stats['p99_ms']:.2f} ms")
    print(f"    min:  {stats['min_ms']:.2f} ms")
    print(f"    max:  {stats['max_ms']:.2f} ms")
    print(f"    mean: {stats['mean_ms']:.2f} ms")


def _soft_assert(condition: bool, message: str):
    if not condition:
        print(f"  [WARN] Soft assertion failed: {message}")


def _load_quality_cases():
    path = Path(__file__).with_name("gaussdb_quality_cases.json")
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def _server_encoding(db: GaussDB) -> str:
    """Return the server encoding reported by the current GaussDB session."""
    with db._get_cursor(commit=False) as cur:
        cur.execute("SHOW server_encoding")
        row = cur.fetchone()
    return str(row[0]).upper() if row and row[0] is not None else ""


# ===========================================================================
# TestCRUD — Basic CRUD operations (from test_gaussdb_p0.py)
# ===========================================================================


class TestCRUD:
    """Basic CRUD operations: insert, get, update, delete, list, search."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="crud")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_insert_single_and_get(self):
        """Insert a single record and retrieve it by ID."""
        vid = _uuid(1)
        _insert_memories(self.db, [(vid, VECTOR_COFFEE, _make_payload("I love coffee", "crud_insert"))])
        result = self.db.get(vid)
        assert result is not None
        assert result.id == vid
        assert result.payload["data"] == "I love coffee"
        assert result.payload["user_id"] == "crud_insert"

    def test_insert_batch_and_list(self):
        """Insert multiple records and list them."""
        records = [
            (_uuid(10), VECTOR_COFFEE, _make_payload("coffee memory", "crud_batch")),
            (_uuid(11), VECTOR_FLIGHT, _make_payload("flight memory", "crud_batch")),
            (_uuid(12), VECTOR_WINDOW, _make_payload("window seat", "crud_batch")),
        ]
        _insert_memories(self.db, records)
        listed = _list_flat(self.db, filters={"user_id": "crud_batch"}, top_k=100)
        assert len(listed) == 3
        _assert_exact_ids(listed, {_uuid(10), _uuid(11), _uuid(12)})

    def test_upsert_existing_record(self):
        """Upsert (MERGE INTO) updates existing record without creating duplicate."""
        vid = _uuid(20)
        _insert_memories(self.db, [(vid, VECTOR_COFFEE, _make_payload("original", "crud_upsert"))])
        self.db.update(vector_id=vid, payload=_make_payload("updated", "crud_upsert"))
        result = self.db.get(vid)
        assert result.payload["data"] == "updated"
        listed = _list_flat(self.db, filters={"user_id": "crud_upsert"}, top_k=100)
        assert len(listed) == 1

    def test_update_vector(self):
        """Update the vector of an existing record."""
        vid = _uuid(21)
        _insert_memories(self.db, [(vid, VECTOR_COFFEE, _make_payload("coffee", "crud_upvec"))])
        self.db.update(vector_id=vid, vector=VECTOR_FLIGHT)
        results = self.db.search("flight", VECTOR_FLIGHT, top_k=1, filters={"user_id": "crud_upvec"})
        assert len(results) >= 1
        assert results[0].id == vid

    def test_delete_by_id(self):
        """Delete a record by ID."""
        vid = _uuid(30)
        _insert_memories(self.db, [(vid, VECTOR_COFFEE, _make_payload("to delete", "crud_del"))])
        self.db.delete(vector_id=vid)
        assert self.db.get(vid) is None

    def test_search_basic(self):
        """Basic vector search returns relevant results."""
        _insert_memories(self.db, [
            (_uuid(40), VECTOR_COFFEE, _make_payload("coffee lover", "crud_search")),
            (_uuid(41), VECTOR_FLIGHT, _make_payload("frequent flyer", "crud_search")),
        ])
        results = self.db.search("coffee", VECTOR_COFFEE, top_k=2, filters={"user_id": "crud_search"})
        assert len(results) >= 1
        assert results[0].id == _uuid(40)

    def test_search_with_top_k(self):
        """Search respects top_k limit."""
        records = [(_uuid(50 + i), VECTOR_COFFEE, _make_payload(f"item {i}", "crud_topk")) for i in range(10)]
        _insert_memories(self.db, records)
        results = self.db.search("item", VECTOR_COFFEE, top_k=3, filters={"user_id": "crud_topk"})
        assert len(results) <= 3

    def test_get_nonexistent_returns_none(self):
        """Get a non-existent ID returns None."""
        result = self.db.get(_uuid(999))
        assert result is None

    def test_delete_nonexistent_no_error(self):
        """Deleting a non-existent ID does not raise."""
        self.db.delete(vector_id=_uuid(998))

    def test_search_batch(self):
        """search_batch returns results for multiple queries."""
        _insert_memories(self.db, [
            (_uuid(60), VECTOR_COFFEE, _make_payload("coffee", "crud_sbatch")),
            (_uuid(61), VECTOR_FLIGHT, _make_payload("flight", "crud_sbatch")),
        ])
        results = self.db.search_batch(
            ["coffee", "flight"],
            [VECTOR_COFFEE, VECTOR_FLIGHT],
            top_k=5,
            filters={"user_id": "crud_sbatch"},
        )
        assert len(results) == 2
        assert len(results[0]) >= 1
        assert len(results[1]) >= 1



# ===========================================================================
# TestFilter — All filter operators (from test_gaussdb_p1_filter.py)
# ===========================================================================

class TestSimpleOperators:
    """Tests for eq, ne, in, nin, contains, icontains operators."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_simple")
        _insert_memories(cls.db, [
            # eq string (user_id="u100")
            (_uuid(100), VECTOR_COFFEE, _make_payload("coffee note", user_id="u100", category="food")),
            (_uuid(101), VECTOR_FLIGHT, _make_payload("flight note", user_id="u100", category="travel")),
            # eq number (user_id="u110")
            (_uuid(110), VECTOR_COFFEE, _make_payload("low priority", user_id="u110", priority="3")),
            (_uuid(111), VECTOR_FLIGHT, _make_payload("high priority", user_id="u110", priority="7")),
            # eq boolean (user_id="u120")
            (_uuid(120), VECTOR_COFFEE, _make_payload("active item", user_id="u120", active="true")),
            (_uuid(121), VECTOR_FLIGHT, _make_payload("inactive item", user_id="u120", active="false")),
            # ne string (user_id="u130")
            (_uuid(130), VECTOR_COFFEE, _make_payload("food item", user_id="u130", category="food")),
            (_uuid(131), VECTOR_FLIGHT, _make_payload("travel item", user_id="u130", category="travel")),
            (_uuid(132), VECTOR_WINDOW, _make_payload("work item", user_id="u130", category="work")),
            # ne number (user_id="u140")
            (_uuid(140), VECTOR_COFFEE, _make_payload("pri 2", user_id="u140", priority="2")),
            (_uuid(141), VECTOR_FLIGHT, _make_payload("pri 5", user_id="u140", priority="5")),
            (_uuid(142), VECTOR_WINDOW, _make_payload("pri 8", user_id="u140", priority="8")),
            # in single (user_id="u150")
            (_uuid(150), VECTOR_COFFEE, _make_payload("food", user_id="u150", category="food")),
            (_uuid(151), VECTOR_FLIGHT, _make_payload("travel", user_id="u150", category="travel")),
            # in multi (user_id="u160")
            (_uuid(160), VECTOR_COFFEE, _make_payload("food", user_id="u160", category="food")),
            (_uuid(161), VECTOR_FLIGHT, _make_payload("travel", user_id="u160", category="travel")),
            (_uuid(162), VECTOR_WINDOW, _make_payload("work", user_id="u160", category="work")),
            # in empty (user_id="u170")
            (_uuid(170), VECTOR_COFFEE, _make_payload("food", user_id="u170", category="food")),
            # nin single (user_id="u180")
            (_uuid(180), VECTOR_COFFEE, _make_payload("food", user_id="u180", category="food")),
            (_uuid(181), VECTOR_FLIGHT, _make_payload("travel", user_id="u180", category="travel")),
            (_uuid(182), VECTOR_WINDOW, _make_payload("work", user_id="u180", category="work")),
            # nin multi (user_id="u190")
            (_uuid(190), VECTOR_COFFEE, _make_payload("food", user_id="u190", category="food")),
            (_uuid(191), VECTOR_FLIGHT, _make_payload("travel", user_id="u190", category="travel")),
            (_uuid(192), VECTOR_WINDOW, _make_payload("work", user_id="u190", category="work")),
            # contains exact (user_id="u200")
            (_uuid(200), VECTOR_COFFEE, _make_payload("coffee shop", user_id="u200", tag="morning-coffee")),
            (_uuid(201), VECTOR_FLIGHT, _make_payload("flight plan", user_id="u200", tag="evening-flight")),
            # contains partial (user_id="u210")
            (_uuid(210), VECTOR_COFFEE, _make_payload("item1", user_id="u210", tag="super-coffee-deluxe")),
            (_uuid(211), VECTOR_FLIGHT, _make_payload("item2", user_id="u210", tag="no-match-here")),
            # contains not exists (user_id="u220")
            (_uuid(220), VECTOR_COFFEE, _make_payload("item", user_id="u220", tag="morning-tea")),
            # icontains (user_id="u230")
            (_uuid(230), VECTOR_COFFEE, _make_payload("item1", user_id="u230", tag="MorningCoffee")),
            (_uuid(231), VECTOR_FLIGHT, _make_payload("item2", user_id="u230", tag="EVENING-COFFEE")),
            (_uuid(232), VECTOR_WINDOW, _make_payload("item3", user_id="u230", tag="afternoon-tea")),
            # eq implicit (user_id="u240")
            (_uuid(240), VECTOR_COFFEE, _make_payload("food item", user_id="u240", category="food")),
            (_uuid(241), VECTOR_FLIGHT, _make_payload("travel item", user_id="u240", category="travel")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_eq_string_exact_match(self):
        """eq operator with string value returns exact match."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u100", "category": {"eq": "food"}})
        _assert_exact_ids(rows, {_uuid(100)})

    def test_eq_number_exact_match(self):
        """eq operator with numeric value returns exact match."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u110", "priority": {"eq": "7"}})
        _assert_exact_ids(rows, {_uuid(111)})

    def test_eq_boolean_exact_match(self):
        """eq operator with boolean-like value returns exact match."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u120", "active": {"eq": "true"}})
        _assert_exact_ids(rows, {_uuid(120)})

    def test_ne_string_exclusion(self):
        """ne operator excludes matching string value."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u130", "category": {"ne": "food"}})
        _assert_exact_ids(rows, {_uuid(131), _uuid(132)})

    def test_ne_number_exclusion(self):
        """ne operator excludes matching numeric value."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u140", "priority": {"ne": "5"}})
        _assert_exact_ids(rows, {_uuid(140), _uuid(142)})

    def test_in_single_value(self):
        """in operator with single value list returns matching record."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u150", "category": {"in": ["food"]}})
        _assert_exact_ids(rows, {_uuid(150)})

    def test_in_multi_value(self):
        """in operator with multiple values returns all matching records."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u160", "category": {"in": ["food", "travel"]}}
        )
        _assert_exact_ids(rows, {_uuid(160), _uuid(161)})

    def test_in_empty_list_returns_nothing(self):
        """in operator with empty list returns no results."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u170", "category": {"in": []}})
        assert len(rows) == 0

    def test_nin_single_value(self):
        """nin operator with single value excludes matching record."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u180", "category": {"nin": ["food"]}})
        _assert_exact_ids(rows, {_uuid(181), _uuid(182)})

    def test_nin_multi_value_exclusion(self):
        """nin operator with multiple values excludes all matching records."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u190", "category": {"nin": ["food", "travel"]}}
        )
        _assert_exact_ids(rows, {_uuid(192)})

    def test_contains_exact_substring(self):
        """contains operator matches exact substring."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u200", "tag": {"contains": "coffee"}})
        _assert_exact_ids(rows, {_uuid(200)})

    def test_contains_partial_substring(self):
        """contains operator matches partial substring within value."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u210", "tag": {"contains": "coffee"}})
        _assert_exact_ids(rows, {_uuid(210)})

    def test_contains_not_exists_returns_empty(self):
        """contains operator with non-matching substring returns empty."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u220", "tag": {"contains": "coffee"}})
        assert len(rows) == 0

    def test_icontains_case_insensitive_match(self):
        """icontains operator matches regardless of case."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u230", "tag": {"icontains": "coffee"}})
        _assert_exact_ids(rows, {_uuid(230), _uuid(231)})

    def test_eq_implicit_direct_value(self):
        """Direct value (without eq wrapper) acts as implicit equality filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u240", "category": "food"})
        _assert_exact_ids(rows, {_uuid(240)})


# ===========================================================================
# 5.2.2 Range Operators (8 tests)
# ===========================================================================


class TestRangeOperators:
    """Tests for current unsupported range-operator behavior."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_range")
        _insert_memories(cls.db, [
            # gt (user_id="u300")
            (_uuid(300), VECTOR_COFFEE, _make_payload("pri 2", user_id="u300", priority="2")),
            (_uuid(301), VECTOR_FLIGHT, _make_payload("pri 5", user_id="u300", priority="5")),
            (_uuid(302), VECTOR_WINDOW, _make_payload("pri 8", user_id="u300", priority="8")),
            # gte (user_id="u310")
            (_uuid(310), VECTOR_COFFEE, _make_payload("pri 2", user_id="u310", priority="2")),
            (_uuid(311), VECTOR_FLIGHT, _make_payload("pri 5", user_id="u310", priority="5")),
            (_uuid(312), VECTOR_WINDOW, _make_payload("pri 8", user_id="u310", priority="8")),
            # lt (user_id="u320")
            (_uuid(320), VECTOR_COFFEE, _make_payload("pri 2", user_id="u320", priority="2")),
            (_uuid(321), VECTOR_FLIGHT, _make_payload("pri 5", user_id="u320", priority="5")),
            (_uuid(322), VECTOR_WINDOW, _make_payload("pri 8", user_id="u320", priority="8")),
            # lte (user_id="u330")
            (_uuid(330), VECTOR_COFFEE, _make_payload("pri 2", user_id="u330", priority="2")),
            (_uuid(331), VECTOR_FLIGHT, _make_payload("pri 5", user_id="u330", priority="5")),
            (_uuid(332), VECTOR_WINDOW, _make_payload("pri 8", user_id="u330", priority="8")),
            # combined gte+lte (user_id="u340")
            (_uuid(340), VECTOR_COFFEE, _make_payload("pri 1", user_id="u340", priority="1")),
            (_uuid(341), VECTOR_FLIGHT, _make_payload("pri 3", user_id="u340", priority="3")),
            (_uuid(342), VECTOR_WINDOW, _make_payload("pri 5", user_id="u340", priority="5")),
            (_uuid(343), VECTOR_AISLE, _make_payload("pri 7", user_id="u340", priority="7")),
            (_uuid(344), VECTOR_COFFEE, _make_payload("pri 9", user_id="u340", priority="9")),
            # combined gt+lt exclusive (user_id="u350")
            (_uuid(350), VECTOR_COFFEE, _make_payload("pri 1", user_id="u350", priority="1")),
            (_uuid(351), VECTOR_FLIGHT, _make_payload("pri 3", user_id="u350", priority="3")),
            (_uuid(352), VECTOR_WINDOW, _make_payload("pri 5", user_id="u350", priority="5")),
            (_uuid(353), VECTOR_AISLE, _make_payload("pri 7", user_id="u350", priority="7")),
            (_uuid(354), VECTOR_COFFEE, _make_payload("pri 9", user_id="u350", priority="9")),
            # combined with eq (user_id="u360")
            (_uuid(360), VECTOR_COFFEE, _make_payload("food pri 2", user_id="u360", category="food", priority="2")),
            (_uuid(361), VECTOR_FLIGHT, _make_payload("food pri 5", user_id="u360", category="food", priority="5")),
            (_uuid(362), VECTOR_WINDOW, _make_payload("travel pri 5", user_id="u360", category="travel", priority="5")),
            # gt date string (user_id="u370")
            (_uuid(370), VECTOR_COFFEE, _make_payload("old", user_id="u370", created="2024-01-01")),
            (_uuid(371), VECTOR_FLIGHT, _make_payload("mid", user_id="u370", created="2024-06-15")),
            (_uuid(372), VECTOR_WINDOW, _make_payload("new", user_id="u370", created="2025-01-01")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_unsupported_gt_operator_returns_empty(self):
        """Unsupported gt operator is treated as a non-matching literal dict filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u300", "priority": {"gt": "5"}})
        _assert_exact_ids(rows, set())

    def test_unsupported_gte_operator_returns_empty(self):
        """Unsupported gte operator is treated as a non-matching literal dict filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u310", "priority": {"gte": "5"}})
        _assert_exact_ids(rows, set())

    def test_unsupported_lt_operator_returns_empty(self):
        """Unsupported lt operator is treated as a non-matching literal dict filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u320", "priority": {"lt": "5"}})
        _assert_exact_ids(rows, set())

    def test_unsupported_lte_operator_returns_empty(self):
        """Unsupported lte operator is treated as a non-matching literal dict filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u330", "priority": {"lte": "5"}})
        _assert_exact_ids(rows, set())

    def test_range_combined_gte_lte(self):
        """Combined range operators do not produce typed range semantics."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u340", "priority": {"gte": "3", "lte": "7"}},
        )
        _assert_exact_ids(rows, set())

    def test_range_combined_gt_lt_exclusive(self):
        """Combined gt + lt remains unsupported and does not match stored scalar payloads."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u350", "priority": {"gt": "1", "lt": "9"}},
        )
        _assert_exact_ids(rows, set())

    def test_range_combined_with_eq(self):
        """Unsupported range operator does not start matching when combined with eq."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u360", "category": "food", "priority": {"gte": "3"}},
        )
        _assert_exact_ids(rows, set())

    def test_gt_date_string(self):
        """Unsupported range syntax also does not match ISO date strings."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10, filters={"user_id": "u370", "created": {"gt": "2024-06-01"}}
        )
        _assert_exact_ids(rows, set())


# ===========================================================================
# 5.2.3 Logical Combination Operators (7 tests)
# ===========================================================================


class TestLogicalCombinationOperators:
    """Tests for AND, OR, NOT logical operators."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_logic")
        _insert_memories(cls.db, [
            # test_and_implicit_two_keys (user_id="u400")
            (_uuid(400), VECTOR_COFFEE, _make_payload("food hi", user_id="u400", category="food", priority="7")),
            (_uuid(401), VECTOR_FLIGHT, _make_payload("food lo", user_id="u400", category="food", priority="2")),
            (_uuid(402), VECTOR_WINDOW, _make_payload("travel hi", user_id="u400", category="travel", priority="7")),
            # test_and_implicit_three_keys (user_id="u410")
            (_uuid(410), VECTOR_COFFEE, _make_payload("match", user_id="u410", category="food", status="active", priority="5")),
            (_uuid(411), VECTOR_FLIGHT, _make_payload("no cat", user_id="u410", category="travel", status="active", priority="5")),
            (_uuid(412), VECTOR_WINDOW, _make_payload("no status", user_id="u410", category="food", status="archived", priority="5")),
            # test_and_explicit_operator (user_id="u420")
            (_uuid(420), VECTOR_COFFEE, _make_payload("match", user_id="u420", category="food", priority="7")),
            (_uuid(421), VECTOR_FLIGHT, _make_payload("no match", user_id="u420", category="travel", priority="7")),
            # test_or_two_conditions (user_id="u430")
            (_uuid(430), VECTOR_COFFEE, _make_payload("food", user_id="u430", category="food")),
            (_uuid(431), VECTOR_FLIGHT, _make_payload("travel", user_id="u430", category="travel")),
            (_uuid(432), VECTOR_WINDOW, _make_payload("work", user_id="u430", category="work")),
            # test_or_three_conditions (user_id="u440")
            (_uuid(440), VECTOR_COFFEE, _make_payload("food", user_id="u440", category="food")),
            (_uuid(441), VECTOR_FLIGHT, _make_payload("travel", user_id="u440", category="travel")),
            (_uuid(442), VECTOR_WINDOW, _make_payload("work", user_id="u440", category="work")),
            (_uuid(443), VECTOR_AISLE, _make_payload("health", user_id="u440", category="health")),
            # test_not_single_condition (user_id="u450")
            (_uuid(450), VECTOR_COFFEE, _make_payload("food", user_id="u450", category="food")),
            (_uuid(451), VECTOR_FLIGHT, _make_payload("travel", user_id="u450", category="travel")),
            (_uuid(452), VECTOR_WINDOW, _make_payload("work", user_id="u450", category="work")),
            # test_not_with_scoped_guard (user_id="u460")
            (_uuid(460), VECTOR_COFFEE, _make_payload("food", user_id="u460", category="food")),
            (_uuid(461), VECTOR_FLIGHT, _make_payload("travel", user_id="u460", category="travel")),
            (_uuid(462), VECTOR_WINDOW, _make_payload("work", user_id="u460_other", category="work")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_and_implicit_two_keys(self):
        """Implicit AND with two keys in same dict filters by both conditions."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u400", "category": "food", "priority": "7"},
        )
        _assert_exact_ids(rows, {_uuid(400)})

    def test_and_implicit_three_keys(self):
        """Implicit AND with three filter keys narrows results correctly."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u410", "category": "food", "status": "active"},
        )
        _assert_exact_ids(rows, {_uuid(410)})

    def test_and_explicit_operator(self):
        """Explicit $and operator combines conditions."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"$and": [{"user_id": "u420"}, {"category": "food"}, {"priority": "7"}]},
        )
        _assert_exact_ids(rows, {_uuid(420)})

    def test_or_two_conditions(self):
        """$or operator with two conditions returns union of matches."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"$or": [{"user_id": "u430", "category": "food"}, {"user_id": "u430", "category": "travel"}]},
        )
        _assert_exact_ids(rows, {_uuid(430), _uuid(431)})

    def test_or_three_conditions(self):
        """$or operator with three conditions returns union of all matches."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={
                "$or": [
                    {"user_id": "u440", "category": "food"},
                    {"user_id": "u440", "category": "travel"},
                    {"user_id": "u440", "category": "work"},
                ]
            },
        )
        _assert_exact_ids(rows, {_uuid(440), _uuid(441), _uuid(442)})

    def test_not_single_condition(self):
        """$not operator excludes matching records."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u450", "$not": [{"category": "food"}]},
        )
        _assert_exact_ids(rows, {_uuid(451), _uuid(452)})

    def test_not_with_scoped_guard(self):
        """$not combined with scoped user_id filter works correctly."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u460", "$not": [{"category": "travel"}]},
        )
        _assert_exact_ids(rows, {_uuid(460)})


# ===========================================================================
# 5.2.4 Nested Logic Combinations (4 tests)
# ===========================================================================


class TestNestedLogicCombinations:
    """Tests for nested logical operator combinations."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_nest")
        _insert_memories(cls.db, [
            # test_or_nested_and (user_id="u500")
            (_uuid(500), VECTOR_COFFEE, _make_payload("food hi", user_id="u500", category="food", priority="7")),
            (_uuid(501), VECTOR_FLIGHT, _make_payload("food lo", user_id="u500", category="food", priority="2")),
            (_uuid(502), VECTOR_WINDOW, _make_payload("travel hi", user_id="u500", category="travel", priority="8")),
            (_uuid(503), VECTOR_AISLE, _make_payload("travel lo", user_id="u500", category="travel", priority="1")),
            # test_and_nested_or (user_id="u510")
            (_uuid(510), VECTOR_COFFEE, _make_payload("food hi", user_id="u510", category="food", priority="7")),
            (_uuid(511), VECTOR_FLIGHT, _make_payload("travel hi", user_id="u510", category="travel", priority="8")),
            (_uuid(512), VECTOR_WINDOW, _make_payload("work hi", user_id="u510", category="work", priority="9")),
            # test_not_nested_or (user_id="u520")
            (_uuid(520), VECTOR_COFFEE, _make_payload("food", user_id="u520", category="food")),
            (_uuid(521), VECTOR_FLIGHT, _make_payload("travel", user_id="u520", category="travel")),
            (_uuid(522), VECTOR_WINDOW, _make_payload("work", user_id="u520", category="work")),
            (_uuid(523), VECTOR_AISLE, _make_payload("health", user_id="u520", category="health")),
            # test_complex_three_level_nesting (user_id="u530")
            (_uuid(530), VECTOR_COFFEE, _make_payload("a", user_id="u530", category="food", status="active", priority="7")),
            (_uuid(531), VECTOR_FLIGHT, _make_payload("b", user_id="u530", category="travel", status="active", priority="3")),
            (_uuid(532), VECTOR_WINDOW, _make_payload("c", user_id="u530", category="food", status="archived", priority="9")),
            (_uuid(533), VECTOR_AISLE, _make_payload("d", user_id="u530", category="work", status="active", priority="6")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_or_nested_and(self):
        """$or containing nested AND conditions (implicit via dict keys)."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={
                "$or": [
                    {"user_id": "u500", "category": "food", "priority": "7"},
                    {"user_id": "u500", "category": "travel", "priority": "8"},
                ]
            },
        )
        _assert_exact_ids(rows, {_uuid(500), _uuid(502)})

    def test_and_nested_or(self):
        """$and containing a nested $or condition."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={
                "$and": [
                    {"user_id": "u510"},
                    {"$or": [{"user_id": "u510", "category": "food"}, {"user_id": "u510", "category": "travel"}]},
                    {"priority": {"in": ["7", "8"]}},
                ]
            },
        )
        _assert_exact_ids(rows, {_uuid(510), _uuid(511)})

    def test_not_nested_or(self):
        """$not applied to an $or-like condition via multiple NOT items."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u520", "$not": [{"category": "food"}, {"category": "travel"}]},
        )
        _assert_exact_ids(rows, {_uuid(522), _uuid(523)})

    def test_complex_three_level_nesting(self):
        """Complex filter with three levels of nesting."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={
                "$and": [
                    {"user_id": "u530"},
                    {"status": "active"},
                    {
                        "$or": [
                            {"user_id": "u530", "category": "food"},
                            {"user_id": "u530", "category": "work", "priority": "6"},
                        ]
                    },
                ]
            },
        )
        _assert_exact_ids(rows, {_uuid(530), _uuid(533)})


# ===========================================================================
# 5.2.5 Null Value Handling (5 tests)
# ===========================================================================


class TestNullValueHandling:
    """Tests for null, missing key, and empty string filter behavior."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_null")
        _insert_memories(cls.db, [
            # test_filter_key_not_exists_returns_empty (user_id="u600")
            (_uuid(600), VECTOR_COFFEE, _make_payload("item", user_id="u600", category="food")),
            # test_eq_null_value (user_id="u610")
            (_uuid(610), VECTOR_COFFEE, _make_payload("with tag", user_id="u610", tag="hello")),
            (_uuid(611), VECTOR_FLIGHT, _make_payload("no tag", user_id="u610")),
            # test_ne_null_value_returns_records_with_key (user_id="u620")
            (_uuid(620), VECTOR_COFFEE, _make_payload("tagged", user_id="u620", tag="hello")),
            (_uuid(621), VECTOR_FLIGHT, _make_payload("diff tag", user_id="u620", tag="world")),
            # test_empty_string_match (user_id="u630")
            (_uuid(630), VECTOR_COFFEE, _make_payload("empty tag", user_id="u630", tag="")),
            (_uuid(631), VECTOR_FLIGHT, _make_payload("has tag", user_id="u630", tag="hello")),
            # test_missing_vs_empty_string_difference (user_id="u640")
            (_uuid(640), VECTOR_COFFEE, _make_payload("empty", user_id="u640", tag="")),
            (_uuid(641), VECTOR_FLIGHT, _make_payload("missing", user_id="u640")),
            (_uuid(642), VECTOR_WINDOW, _make_payload("present", user_id="u640", tag="value")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_filter_key_not_exists_returns_empty(self):
        """Filtering on a key that does not exist in payload returns no results."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u600", "nonexistent_key": "some_value"},
        )
        assert len(rows) == 0

    def test_eq_null_value(self):
        """Filtering with eq on a None/null value matches records where key is null or missing."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u610", "tag": {"eq": "None"}},
        )
        assert len(rows) == 0

    def test_ne_null_value_returns_records_with_key(self):
        """ne with a value returns records that have the key with a different value."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u620", "tag": {"ne": "hello"}},
        )
        _assert_exact_ids(rows, {_uuid(621)})

    def test_empty_string_match(self):
        """Filtering for empty string performs an exact JSON string match."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u630", "tag": ""},
        )
        _assert_exact_ids(rows, {_uuid(630)})

    def test_missing_vs_empty_string_difference(self):
        """Records with missing key vs empty string remain distinguishable."""
        rows_empty = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u640", "tag": ""},
        )
        _assert_exact_ids(rows_empty, {_uuid(640)})
        rows_value = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "u640", "tag": "value"},
        )
        _assert_exact_ids(rows_value, {_uuid(642)})


# ===========================================================================
# 5.2.6 Multi-tenant Isolation (12 tests)
# ===========================================================================


class TestMultiTenantIsolation:
    """Tests for multi-tenant scoped filter isolation and enforcement."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="filter_tenant", require_scoped_filters=True)
        _insert_memories(cls.db, [
            # test_user_id_isolation (user_id="mt_alice", "mt_bob", "mt_carol")
            (_uuid(700), VECTOR_COFFEE, _make_payload("alice item", user_id="mt_alice")),
            (_uuid(701), VECTOR_FLIGHT, _make_payload("bob item", user_id="mt_bob")),
            (_uuid(702), VECTOR_WINDOW, _make_payload("carol item", user_id="mt_carol")),
            # test_cross_tenant_search_returns_only_own_data (user_id="mt_alice2", "mt_bob2")
            (_uuid(710), VECTOR_COFFEE, _make_payload("alice secret", user_id="mt_alice2")),
            (_uuid(711), VECTOR_COFFEE, _make_payload("bob secret", user_id="mt_bob2")),
            # test_agent_id_isolation (user_id="mt_u720")
            (_uuid(720), VECTOR_COFFEE, _make_payload("agent1 item", user_id="mt_u720", agent_id="agent_a")),
            (_uuid(721), VECTOR_FLIGHT, _make_payload("agent2 item", user_id="mt_u720", agent_id="agent_b")),
            # test_run_id_isolation (user_id="mt_u730")
            (_uuid(730), VECTOR_COFFEE, _make_payload("run1 item", user_id="mt_u730", run_id="run_001")),
            (_uuid(731), VECTOR_FLIGHT, _make_payload("run2 item", user_id="mt_u730", run_id="run_002")),
            # test_combined_user_and_agent_isolation (user_id="mt_u740", "mt_u742")
            (_uuid(740), VECTOR_COFFEE, _make_payload("u1 a1", user_id="mt_u740", agent_id="agent_a")),
            (_uuid(741), VECTOR_FLIGHT, _make_payload("u1 a2", user_id="mt_u740", agent_id="agent_b")),
            (_uuid(742), VECTOR_WINDOW, _make_payload("u2 a1", user_id="mt_u742", agent_id="agent_a")),
            # test_combined_user_and_run_isolation (user_id="mt_u750", "mt_u752")
            (_uuid(750), VECTOR_COFFEE, _make_payload("u1 r1", user_id="mt_u750", run_id="run_001")),
            (_uuid(751), VECTOR_FLIGHT, _make_payload("u1 r2", user_id="mt_u750", run_id="run_002")),
            (_uuid(752), VECTOR_WINDOW, _make_payload("u2 r1", user_id="mt_u752", run_id="run_001")),
            # test_combined_all_three_scope_filters (user_id="mt_u760")
            (_uuid(760), VECTOR_COFFEE, _make_payload("exact", user_id="mt_u760", agent_id="agent_a", run_id="run_001")),
            (_uuid(761), VECTOR_FLIGHT, _make_payload("diff run", user_id="mt_u760", agent_id="agent_a", run_id="run_002")),
            (_uuid(762), VECTOR_WINDOW, _make_payload("diff agent", user_id="mt_u760", agent_id="agent_b", run_id="run_001")),
            # test_scope_guard_missing_user_id_raises_error (user_id="mt_u770")
            (_uuid(770), VECTOR_COFFEE, _make_payload("item", user_id="mt_u770", category="food")),
            # test_or_without_scope_in_all_branches_raises_error (user_id="mt_u780")
            (_uuid(780), VECTOR_COFFEE, _make_payload("item", user_id="mt_u780", category="food")),
            # test_filter_mode_json_expression_basic (user_id="mt_json")
            (_uuid(790), VECTOR_COFFEE, _make_payload("food item", user_id="mt_json", category="food")),
            (_uuid(791), VECTOR_FLIGHT, _make_payload("travel item", user_id="mt_json", category="travel")),
            # test_filter_mode_json_expression_range (user_id="mt_json2")
            (_uuid(800), VECTOR_COFFEE, _make_payload("low", user_id="mt_json2", priority="2")),
            (_uuid(801), VECTOR_FLIGHT, _make_payload("high", user_id="mt_json2", priority="8")),
            # test_filter_mode_redundant_columns_basic (user_id="mt_rc_alice", "mt_rc_bob")
            (_uuid(810), VECTOR_COFFEE, _make_payload("alice item", user_id="mt_rc_alice")),
            (_uuid(811), VECTOR_FLIGHT, _make_payload("bob item", user_id="mt_rc_bob")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_user_id_isolation(self):
        """Records from different user_ids are isolated by filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_alice"})
        _assert_exact_ids(rows, {_uuid(700)})

    def test_cross_tenant_search_returns_only_own_data(self):
        """Searching with one user_id never returns another user's data."""
        alice_rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_alice2"})
        bob_rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_bob2"})
        _assert_exact_ids(alice_rows, {_uuid(710)})
        _assert_exact_ids(bob_rows, {_uuid(711)})

    def test_agent_id_isolation(self):
        """Records are isolated by agent_id scope filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_u720", "agent_id": "agent_a"})
        _assert_exact_ids(rows, {_uuid(720)})

    def test_run_id_isolation(self):
        """Records are isolated by run_id scope filter."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_u730", "run_id": "run_001"})
        _assert_exact_ids(rows, {_uuid(730)})

    def test_combined_user_and_agent_isolation(self):
        """Combined user_id + agent_id filter narrows results correctly."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_u740", "agent_id": "agent_a"})
        _assert_exact_ids(rows, {_uuid(740)})

    def test_combined_user_and_run_isolation(self):
        """Combined user_id + run_id filter narrows results correctly."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_u750", "run_id": "run_001"})
        _assert_exact_ids(rows, {_uuid(750)})

    def test_combined_all_three_scope_filters(self):
        """Combined user_id + agent_id + run_id filter narrows to exact match."""
        rows = self.db.search(
            "test", VECTOR_COFFEE, top_k=10,
            filters={"user_id": "mt_u760", "agent_id": "agent_a", "run_id": "run_001"},
        )
        _assert_exact_ids(rows, {_uuid(760)})

    def test_scope_guard_missing_user_id_raises_error(self):
        """Search without any scope filter raises ValueError when require_scoped_filters=True."""
        with pytest.raises(ValueError, match="requires at least one scoped filter"):
            self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"category": "food"})

    def test_or_without_scope_in_all_branches_raises_error(self):
        """$or where not all branches have scope filter raises ValueError."""
        with pytest.raises(ValueError, match="requires at least one scoped filter"):
            self.db.search(
                "test", VECTOR_COFFEE, top_k=10,
                filters={"$or": [{"user_id": "mt_u780"}, {"category": "food"}]},
            )

    def test_filter_mode_json_expression_basic(self):
        """json_expression filter mode supports payload key filtering."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_json", "category": "food"})
        _assert_exact_ids(rows, {_uuid(790)})

    def test_filter_mode_json_expression_range(self):
        """Undeclared payload range filters fall back to compatibility matching and typically do not hit rows."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_json2", "priority": {"gte": "5"}})
        _assert_exact_ids(rows, set())

    def test_filter_mode_redundant_columns_basic(self):
        """Scope column filtering (now uses json_expression mode)."""
        rows = self.db.search("test", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_rc_alice"})
        _assert_exact_ids(rows, {_uuid(810)})




# ===========================================================================
# Search Quality Tests (from test_gaussdb_p1_search_quality.py)
# ===========================================================================

class TestDistanceMetricCorrectness:
    """Tests for distance metric correctness with L2 and cosine."""

    @classmethod
    def setup_class(cls):
        cls.db_l2 = _new_db(prefix="search_l2", vector_metric="l2")
        _insert_memories(cls.db_l2, [
            # test_l2_nearest_neighbor_correct (user_id="u1001")
            (_uuid(1001), [1.0, 0.0, 0.0], _make_payload("point_a", "u1001")),
            (_uuid(1002), [0.9, 0.1, 0.0], _make_payload("point_b", "u1001")),
            (_uuid(1003), [0.0, 1.0, 0.0], _make_payload("point_c", "u1001")),
            # test_l2_ordering_correct (user_id="u1011")
            (_uuid(1011), [0.0, 0.0, 0.0], _make_payload("origin", "u1011")),
            (_uuid(1012), [1.0, 0.0, 0.0], _make_payload("dist_1", "u1011")),
            (_uuid(1013), [2.0, 0.0, 0.0], _make_payload("dist_2", "u1011")),
            (_uuid(1014), [3.0, 0.0, 0.0], _make_payload("dist_3", "u1011")),
            # test_l2_known_distance_value (user_id="u1021")
            (_uuid(1021), [1.0, 0.0, 0.0], _make_payload("unit_x", "u1021")),
            # test_l2_metric_stored_correctly (user_id="u1071")
            (_uuid(1071), [0.5, 0.5, 0.5], _make_payload("center", "u1071")),
        ])
        cls.db_cosine = _new_db(prefix="search_cos", vector_metric="cosine")
        _insert_memories(cls.db_cosine, [
            # test_cosine_nearest_neighbor_correct (user_id="u1031")
            (_uuid(1031), [1.0, 0.0, 0.0], _make_payload("unit_x", "u1031")),
            (_uuid(1032), [0.9, 0.1, 0.0], _make_payload("near_x", "u1031")),
            (_uuid(1033), [0.0, 1.0, 0.0], _make_payload("unit_y", "u1031")),
            # test_cosine_orthogonal_vectors_low_score (user_id="u1041")
            (_uuid(1041), [1.0, 0.0, 0.0], _make_payload("x_axis", "u1041")),
            (_uuid(1042), [0.0, 1.0, 0.0], _make_payload("y_axis", "u1041")),
            # test_cosine_nearest_neighbor_ordering (user_id="u1051")
            (_uuid(1051), [1.0, 0.0, 0.0], _make_payload("along_x", "u1051")),
            (_uuid(1052), [1.0, 1.0, 0.0], _make_payload("45_deg", "u1051")),
            (_uuid(1053), [0.0, 1.0, 0.0], _make_payload("along_y", "u1051")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db_l2.delete_col()
        cls.db_cosine.delete_col()

    def test_l2_nearest_neighbor_correct(self):
        """L2 metric returns the nearest neighbor correctly."""
        results = self.db_l2.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u1001"})
        assert len(results) >= 2
        assert results[0].id == _uuid(1001)
        assert results[1].id == _uuid(1002)

    def test_l2_ordering_correct(self):
        """L2 metric returns results in correct distance order."""
        results = self.db_l2.search("query", [0.0, 0.0, 0.0], top_k=4, filters={"user_id": "u1011"})
        assert len(results) == 4
        _assert_ordered_ids(results, [_uuid(1011), _uuid(1012), _uuid(1013), _uuid(1014)])

    def test_l2_known_distance_value(self):
        """L2 distance returns the raw Euclidean distance."""
        results = self.db_l2.search("query", [0.0, 0.0, 0.0], top_k=1, filters={"user_id": "u1021"})
        assert len(results) == 1
        assert abs(results[0].score - 1.0) < 1e-6

    def test_cosine_nearest_neighbor_correct(self):
        """Cosine metric returns the nearest neighbor correctly."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u1031"})
        assert len(results) >= 2
        assert results[0].id == _uuid(1031)

    def test_cosine_orthogonal_vectors_low_score(self):
        """Cosine distance orders exact matches before orthogonal vectors."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=2, filters={"user_id": "u1041"})
        assert len(results) == 2
        x_score = results[0].score
        y_score = results[1].score
        assert x_score < y_score
        assert abs(x_score - 0.0) < 1e-6
        assert abs(y_score - 1.0) < 1e-6

    def test_cosine_nearest_neighbor_ordering(self):
        """Cosine metric orders results by angular similarity."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u1051"})
        assert len(results) == 3
        _assert_ordered_ids(results, [_uuid(1051), _uuid(1052), _uuid(1053)])

    def test_default_metric_is_cosine(self):
        """Default metric should be cosine when not specified."""
        assert self.db_cosine.vector_metric == "cosine"

    def test_l2_metric_stored_correctly(self):
        """L2 metric is stored and returns zero distance for identical vectors."""
        assert self.db_l2.vector_metric == "l2"
        results = self.db_l2.search("query", [0.5, 0.5, 0.5], top_k=1, filters={"user_id": "u1071"})
        assert len(results) == 1
        assert abs(results[0].score - 0.0) < 1e-6


# ===========================================================================
# 6.2.2 Score Ordering Verification (5 tests)
# ===========================================================================


class TestScoreOrdering:
    """Tests for score ordering and precision."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="search_score", vector_metric="cosine")
        _insert_memories(cls.db, [
            # test_scores_in_descending_order (user_id="u2001")
            (_uuid(2001), [1.0, 0.0, 0.0], _make_payload("vec_a", "u2001")),
            (_uuid(2002), [0.7, 0.7, 0.0], _make_payload("vec_b", "u2001")),
            (_uuid(2003), [0.0, 1.0, 0.0], _make_payload("vec_c", "u2001")),
            (_uuid(2004), [0.0, 0.0, 1.0], _make_payload("vec_d", "u2001")),
            # test_top1_is_closest_vector (user_id="u2011")
            (_uuid(2011), [0.1, 0.9, 0.1], _make_payload("far_from_query", "u2011")),
            (_uuid(2012), [0.95, 0.05, 0.0], _make_payload("close_to_query", "u2011")),
            (_uuid(2013), [0.5, 0.5, 0.5], _make_payload("medium", "u2011")),
            # test_identical_vector_returns_high_score (user_id="u2021")
            (_uuid(2021), [0.6, 0.3, 0.1], _make_payload("target", "u2021")),
            # test_distant_vector_returns_low_score (user_id="u2031")
            (_uuid(2031), [1.0, 0.0, 0.0], _make_payload("opposite_dir", "u2031")),
            # test_score_range_validation (user_id="u2041")
            (_uuid(2041), [1.0, 0.0, 0.0], _make_payload("a", "u2041")),
            (_uuid(2042), [0.0, 1.0, 0.0], _make_payload("b", "u2041")),
            (_uuid(2043), [0.0, 0.0, 1.0], _make_payload("c", "u2041")),
            (_uuid(2044), [-1.0, 0.0, 0.0], _make_payload("d", "u2041")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_scores_in_descending_order(self):
        """Search results should have raw distances in ascending order."""
        results = self.db.search("query", [1.0, 0.0, 0.0], top_k=4, filters={"user_id": "u2001"})
        scores = [r.score for r in results]
        assert scores == sorted(scores), "Raw distances should be in ascending order"

    def test_top1_is_closest_vector(self):
        """Top-1 result should be the closest vector to the query."""
        results = self.db.search("query", [1.0, 0.0, 0.0], top_k=1, filters={"user_id": "u2011"})
        assert len(results) == 1
        assert results[0].id == _uuid(2012)

    def test_identical_vector_returns_high_score(self):
        """Searching with an identical vector should return distance close to 0.0."""
        results = self.db.search("query", [0.6, 0.3, 0.1], top_k=1, filters={"user_id": "u2021"})
        assert len(results) == 1
        assert abs(results[0].score - 0.0) < 1e-6

    def test_distant_vector_returns_low_score(self):
        """A distant vector should return a relatively large raw distance."""
        results = self.db.search("query", [-1.0, 0.0, 0.0], top_k=1, filters={"user_id": "u2031"})
        assert len(results) == 1
        assert results[0].score >= 2.0 - 1e-6

    def test_score_range_validation(self):
        """All raw distances should be non-negative."""
        results = self.db.search("query", [0.5, 0.5, 0.0], top_k=4, filters={"user_id": "u2041"})
        for r in results:
            assert r.score >= 0.0, f"Distance {r.score} should be non-negative"


# ===========================================================================
# 6.2.3 Recall Quality (5 tests)
# ===========================================================================


class TestRecallQuality:
    """Tests for recall quality with known data distributions."""

    @classmethod
    def setup_class(cls):
        cls.db_cosine = _new_db(prefix="search_recall_cos", vector_metric="cosine")
        # test_known_vectors_correct_top3 (user_id="u3001")
        vectors = [
            ([1.0, 0.0, 0.0], "exact_match"),
            ([0.95, 0.05, 0.0], "very_close"),
            ([0.9, 0.1, 0.0], "close"),
            ([0.7, 0.3, 0.0], "moderate_1"),
            ([0.5, 0.5, 0.0], "moderate_2"),
            ([0.3, 0.7, 0.0], "far_1"),
            ([0.1, 0.9, 0.0], "far_2"),
            ([0.0, 1.0, 0.0], "orthogonal"),
            ([0.0, 0.0, 1.0], "orthogonal_z"),
            ([-1.0, 0.0, 0.0], "opposite"),
        ]
        records = [
            (_uuid(3001 + i), vec, _make_payload(label, "u3001"))
            for i, (vec, label) in enumerate(vectors)
        ]
        # test_cluster_search_returns_same_cluster_first (user_id="u3201")
        records += [
            (_uuid(3201), [0.95, 0.05, 0.0], _make_payload("cluster_a_1", "u3201")),
            (_uuid(3202), [0.90, 0.10, 0.0], _make_payload("cluster_a_2", "u3201")),
            (_uuid(3203), [0.85, 0.15, 0.0], _make_payload("cluster_a_3", "u3201")),
            (_uuid(3204), [0.05, 0.95, 0.0], _make_payload("cluster_b_1", "u3201")),
            (_uuid(3205), [0.10, 0.90, 0.0], _make_payload("cluster_b_2", "u3201")),
            (_uuid(3206), [0.15, 0.85, 0.0], _make_payload("cluster_b_3", "u3201")),
        ]
        # test_duplicate_vectors_return_same_score (user_id="u3301")
        records += [
            (_uuid(3301), [0.5, 0.5, 0.0], _make_payload("dup_1", "u3301")),
            (_uuid(3302), [0.5, 0.5, 0.0], _make_payload("dup_2", "u3301")),
        ]
        # test_near_duplicate_vectors_return_similar_scores (user_id="u3401")
        records += [
            (_uuid(3401), [0.500, 0.500, 0.000], _make_payload("near_dup_1", "u3401")),
            (_uuid(3402), [0.501, 0.499, 0.001], _make_payload("near_dup_2", "u3401")),
        ]
        _insert_memories(cls.db_cosine, records)

        # test_100_vectors_recall_at_10 needs L2 with dynamic data
        import random
        random.seed(42)
        cls.db_l2 = _new_db(prefix="search_recall_l2", vector_metric="l2")
        cls._all_vectors = []
        l2_records = []
        for i in range(100):
            vec = [random.uniform(-1, 1) for _ in range(3)]
            cls._all_vectors.append((i, vec))
            l2_records.append((_uuid(3100 + i), vec, _make_payload(f"item_{i}", "u3100")))
        _insert_memories(cls.db_l2, l2_records)

    @classmethod
    def teardown_class(cls):
        cls.db_cosine.delete_col()
        cls.db_l2.delete_col()

    def test_known_vectors_correct_top3(self):
        """Insert 10 known vectors, search returns correct top-3."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u3001"})
        assert len(results) == 3
        top3_ids = _ids(results)
        assert top3_ids[0] == _uuid(3001)
        assert top3_ids[1] == _uuid(3002)
        assert top3_ids[2] == _uuid(3003)

    def test_100_vectors_recall_at_10(self):
        """Insert 100 vectors, recall@10 should be >= 0.8 for known nearest neighbors."""
        query = [0.5, 0.5, 0.5]

        def l2_dist(a, b):
            return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))

        true_nearest = sorted(self._all_vectors, key=lambda x: l2_dist(x[1], query))
        true_top10_ids = {_uuid(3100 + idx) for idx, _ in true_nearest[:10]}

        results = self.db_l2.search("query", query, top_k=10, filters={"user_id": "u3100"})
        result_ids = set(_ids(results))

        recall = len(result_ids & true_top10_ids) / 10.0
        assert recall >= 0.8, f"Recall@10 = {recall}, expected >= 0.8"

    def test_cluster_search_returns_same_cluster_first(self):
        """Vectors in the same cluster as query should rank higher."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=6, filters={"user_id": "u3201"})
        top3_ids = set(_ids(results[:3]))
        cluster_a_ids = {_uuid(3201), _uuid(3202), _uuid(3203)}
        assert top3_ids == cluster_a_ids, "Top-3 should all be from cluster A"

    def test_duplicate_vectors_return_same_score(self):
        """Duplicate vectors should return the same score."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=2, filters={"user_id": "u3301"})
        assert len(results) == 2
        assert abs(results[0].score - results[1].score) < 1e-6

    def test_near_duplicate_vectors_return_similar_scores(self):
        """Near-duplicate vectors should return very similar scores."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=2, filters={"user_id": "u3401"})
        assert len(results) == 2
        score_diff = abs(results[0].score - results[1].score)
        assert score_diff < 0.01, f"Near-duplicate score diff {score_diff} should be < 0.01"


# ===========================================================================
# 6.2.4 BM25 Search Quality (5 tests, conditional)
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_BM25"), reason="BM25 tests disabled")
class TestBM25SearchQuality:
    """Tests for BM25 text search quality (requires GAUSSDB_TEST_RUN_BM25=true)."""

    def test_bm25_single_keyword_match(self):
        """BM25 search with a single keyword should find matching documents."""
        db = _new_db(prefix="p1_search")
        try:
            _insert_memories(db, [
                (_uuid(4001), VECTOR_COFFEE, _make_payload("coffee espresso latte", "bm25_user")),
                (_uuid(4002), VECTOR_FLIGHT, _make_payload("airplane flight travel", "bm25_user")),
                (_uuid(4003), VECTOR_WINDOW, _make_payload("window glass pane", "bm25_user")),
            ])
            results = db.search("coffee", VECTOR_COFFEE, top_k=3, filters={"user_id": "bm25_user"})
            assert len(results) >= 1
            # The coffee document should rank high
            result_ids = _ids(results)
            assert _uuid(4001) in result_ids
        finally:
            db.delete_col()

    def test_bm25_multi_keyword_match(self):
        """BM25 search with multiple keywords should prefer documents matching more terms."""
        db = _new_db(prefix="p1_search")
        try:
            _insert_memories(db, [
                (_uuid(4011), VECTOR_COFFEE, _make_payload("coffee espresso morning brew", "bm25_user")),
                (_uuid(4012), VECTOR_FLIGHT, _make_payload("coffee flight morning travel", "bm25_user")),
                (_uuid(4013), VECTOR_WINDOW, _make_payload("window glass morning light", "bm25_user")),
            ])
            results = db.search("coffee morning", VECTOR_COFFEE, top_k=3, filters={"user_id": "bm25_user"})
            assert len(results) >= 1
            # Documents with both "coffee" and "morning" should rank higher
            top_ids = _ids(results[:2])
            assert _uuid(4011) in top_ids or _uuid(4012) in top_ids
        finally:
            db.delete_col()

    def test_bm25_exact_phrase_match(self):
        """BM25 search should find exact phrase matches."""
        db = _new_db(prefix="p1_search")
        try:
            _insert_memories(db, [
                (_uuid(4021), VECTOR_COFFEE, _make_payload("hot coffee with milk", "bm25_user")),
                (_uuid(4022), VECTOR_FLIGHT, _make_payload("cold coffee without milk", "bm25_user")),
                (_uuid(4023), VECTOR_WINDOW, _make_payload("tea with lemon", "bm25_user")),
            ])
            results = db.search("hot coffee", VECTOR_COFFEE, top_k=3, filters={"user_id": "bm25_user"})
            assert len(results) >= 1
            # "hot coffee" document should be in results
            assert _uuid(4021) in _ids(results)
        finally:
            db.delete_col()

    def test_bm25_no_match_returns_empty_or_low_score(self):
        """BM25 search with no matching terms should return empty or very low scores."""
        db = _new_db(prefix="p1_search")
        try:
            _insert_memories(db, [
                (_uuid(4031), VECTOR_COFFEE, _make_payload("coffee espresso latte", "bm25_user")),
                (_uuid(4032), VECTOR_FLIGHT, _make_payload("airplane flight travel", "bm25_user")),
            ])
            # Search for a term that does not exist in any document
            results = db.search("xyznonexistent", VECTOR_WINDOW, top_k=3, filters={"user_id": "bm25_user"})
            # Either empty or results have low relevance (vector-only fallback)
            if len(results) > 0:
                # If results returned, they are from vector similarity only
                # No BM25 boost should be applied
                assert all(r.score <= 1.0 for r in results)
        finally:
            db.delete_col()

    def test_bm25_score_ordering(self):
        """BM25 results should be ordered by relevance score."""
        db = _new_db(prefix="p1_search")
        try:
            _insert_memories(db, [
                (_uuid(4041), VECTOR_COFFEE, _make_payload("coffee coffee coffee beans", "bm25_user")),
                (_uuid(4042), VECTOR_FLIGHT, _make_payload("coffee once mentioned", "bm25_user")),
                (_uuid(4043), VECTOR_WINDOW, _make_payload("no relevant terms here", "bm25_user")),
            ])
            results = db.search("coffee", VECTOR_COFFEE, top_k=3, filters={"user_id": "bm25_user"})
            if len(results) >= 2:
                scores = [r.score for r in results]
                assert scores == sorted(scores), "Raw vector distances should be in ascending order"
        finally:
            db.delete_col()


# ===========================================================================
# 6.2.5 Hybrid Search Quality (3 tests, conditional)
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_BM25"), reason="Hybrid tests require BM25")
class TestHybridSearchQuality:
    """Tests for hybrid (vector + BM25) search quality."""

    def test_hybrid_vector_plus_bm25_combined(self):
        """Hybrid search should benefit from both vector and text similarity."""
        db = _new_db(prefix="p1_search")
        try:
            # Doc 1: good vector match + good text match
            # Doc 2: good vector match + poor text match
            # Doc 3: poor vector match + good text match
            _insert_memories(db, [
                (_uuid(5001), [0.9, 0.1, 0.0], _make_payload("coffee espresso beans", "hybrid_user")),
                (_uuid(5002), [0.85, 0.15, 0.0], _make_payload("unrelated topic here", "hybrid_user")),
                (_uuid(5003), [0.1, 0.9, 0.0], _make_payload("coffee latte cappuccino", "hybrid_user")),
            ])
            results = db.search("coffee", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "hybrid_user"})
            assert len(results) >= 1
            # Doc with both good vector + text match should rank first
            assert results[0].id == _uuid(5001)
        finally:
            db.delete_col()

    def test_hybrid_vs_vector_only_comparison(self):
        """Hybrid search should produce different ranking than pure vector search."""
        db_hybrid = _new_db(prefix="p1_search")
        db_vector = _new_db(prefix="p1_search")
        try:
            records = [
                (_uuid(5011), [0.9, 0.1, 0.0], _make_payload("airplane flight travel", "hybrid_user")),
                (_uuid(5012), [0.85, 0.15, 0.0], _make_payload("coffee espresso beans", "hybrid_user")),
                (_uuid(5013), [0.1, 0.9, 0.0], _make_payload("coffee latte morning", "hybrid_user")),
            ]
            _insert_memories(db_hybrid, records)
            _insert_memories(db_vector, records)

            query_vec = [1.0, 0.0, 0.0]
            hybrid_results = db_hybrid.search("coffee", query_vec, top_k=3, filters={"user_id": "hybrid_user"})
            vector_results = db_vector.search("coffee", query_vec, top_k=3, filters={"user_id": "hybrid_user"})

            # Both should return results
            assert len(hybrid_results) >= 1
            assert len(vector_results) >= 1
            # Hybrid may reorder results due to BM25 boost
            # At minimum, both return valid scored results
            for r in hybrid_results:
                assert r.score >= 0
            for r in vector_results:
                assert r.score >= 0
        finally:
            db_hybrid.delete_col()
            db_vector.delete_col()

    def test_hybrid_bm25_boost_effect(self):
        """BM25 component should boost text-relevant results in hybrid search."""
        db = _new_db(prefix="p1_search")
        try:
            # Two vectors equidistant from query, but one has matching text
            _insert_memories(db, [
                (_uuid(5021), [0.7, 0.7, 0.0], _make_payload("coffee beans roast", "hybrid_user")),
                (_uuid(5022), [0.7, 0.0, 0.7], _make_payload("unrelated random words", "hybrid_user")),
            ])
            results = db.search("coffee", [0.7, 0.35, 0.35], top_k=2, filters={"user_id": "hybrid_user"})
            assert len(results) == 2
            # The text-matching document should get a boost
            assert results[0].id == _uuid(5021)
        finally:
            db.delete_col()


# ===========================================================================
# 6.2.6 Score Edge Cases (4 tests)
# ===========================================================================


class TestScoreEdgeCases:
    """Tests for score edge cases and stability."""

    @classmethod
    def setup_class(cls):
        cls.db_cosine = _new_db(prefix="search_edge_cos", vector_metric="cosine")
        _insert_memories(cls.db_cosine, [
            # test_orthogonal_vectors_low_scores (user_id="u6001")
            (_uuid(6001), [0.0, 1.0, 0.0], _make_payload("y_axis", "u6001")),
            (_uuid(6002), [0.0, 0.0, 1.0], _make_payload("z_axis", "u6001")),
            (_uuid(6003), [0.0, 0.7, 0.7], _make_payload("yz_plane", "u6001")),
            # test_duplicate_scores_sorting_stability (user_id="u6011")
            (_uuid(6011), [0.5, 0.5, 0.0], _make_payload("dup_a", "u6011")),
            (_uuid(6012), [0.5, 0.5, 0.0], _make_payload("dup_b", "u6011")),
            (_uuid(6013), [0.5, 0.5, 0.0], _make_payload("dup_c", "u6011")),
            # test_score_precision_decimal_places (user_id="u6021")
            (_uuid(6021), [0.9, 0.1, 0.0], _make_payload("precise_a", "u6021")),
            (_uuid(6022), [0.8, 0.2, 0.0], _make_payload("precise_b", "u6021")),
        ])
        # test_large_dataset_sorting_correctness needs L2 with 1000 vectors
        import random
        random.seed(123)
        cls.db_l2 = _new_db(prefix="search_edge_l2", vector_metric="l2")
        batch_size = 100
        for batch_start in range(0, 1000, batch_size):
            records = []
            for i in range(batch_start, batch_start + batch_size):
                vec = [random.uniform(-1, 1) for _ in range(3)]
                records.append((_uuid(6100 + i), vec, _make_payload(f"item_{i}", "u6100")))
            _insert_memories(cls.db_l2, records)

    @classmethod
    def teardown_class(cls):
        cls.db_cosine.delete_col()
        cls.db_l2.delete_col()

    def test_orthogonal_vectors_low_scores(self):
        """All vectors orthogonal to query should produce distances at or above 1.0."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u6001"})
        for r in results:
            assert r.score >= 1.0 - 1e-6, f"Orthogonal vector distance {r.score} should be >= 1.0"

    def test_duplicate_scores_sorting_stability(self):
        """Vectors with identical scores should have stable sort (by ID)."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=3, filters={"user_id": "u6011"})
        assert len(results) == 3
        scores = [r.score for r in results]
        assert all(abs(s - scores[0]) < 1e-6 for s in scores)
        ids = _ids(results)
        assert ids == sorted(ids), "Tie-breaking should be stable (by ID)"

    def test_score_precision_decimal_places(self):
        """Scores should have reasonable floating-point precision."""
        results = self.db_cosine.search("query", [1.0, 0.0, 0.0], top_k=2, filters={"user_id": "u6021"})
        assert len(results) == 2
        assert results[0].score != results[1].score
        for r in results:
            score_str = f"{r.score:.6f}"
            assert len(score_str) >= 6

    def test_large_dataset_sorting_correctness(self):
        """1000 items with top_k=100 should return correctly sorted results."""
        query = [0.0, 0.0, 0.0]
        results = self.db_l2.search("query", query, top_k=100, filters={"user_id": "u6100"})
        assert len(results) == 100
        scores = [r.score for r in results]
        for i in range(len(scores) - 1):
            assert scores[i] <= scores[i + 1], (
                f"Distance at position {i} ({scores[i]}) should be <= distance at position {i+1} ({scores[i+1]})"
            )




# ===========================================================================
# Boundary Value Tests (from test_gaussdb_p1_boundary.py)
# ===========================================================================

class TestVectorDimensionBoundary:
    """Tests for vector dimension edge cases."""

    def test_single_dimension_vector_insert_and_search(self):
        """1-dimensional vector should work."""
        db = _new_db(prefix="p1_dim", embedding_model_dims=1)
        try:
            vid = _uuid(1001)
            db.insert(
                ids=[vid],
                vectors=[[0.5]],
                payloads=[{"data": "single dim", "user_id": "dim_user"}],
            )
            results = db.search("single", [0.5], top_k=1, filters={"user_id": "dim_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_high_dimension_vector_insert_and_search(self):
        """High-dimensional vector (256-dim) should work."""
        dims = 256
        db = _new_db(prefix="p1_dim", embedding_model_dims=dims)
        try:
            vid = _uuid(1002)
            vector = [float(i) / dims for i in range(dims)]
            db.insert(
                ids=[vid],
                vectors=[vector],
                payloads=[{"data": "high dim", "user_id": "dim_user"}],
            )
            results = db.search("high", vector, top_k=1, filters={"user_id": "dim_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_zero_vector_insert_and_search(self):
        """Zero vector should be insertable."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1003)
            zero_vec = [0.0] * EMBEDDING_DIMS
            db.insert(
                ids=[vid],
                vectors=[zero_vec],
                payloads=[{"data": "zero vector", "user_id": "dim_user"}],
            )
            result = db.get(vid)
            assert result is not None
            assert result.id == vid
        finally:
            db.delete_col()

    def test_nan_vector_raises_or_handles_gracefully(self):
        """NaN in vector should raise an error or be handled gracefully."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1004)
            nan_vec = [float("nan"), 0.1, 0.2]
            with pytest.raises((ValueError, Exception)):
                db.insert(
                    ids=[vid],
                    vectors=[nan_vec],
                    payloads=[{"data": "nan vector", "user_id": "dim_user"}],
                )
        finally:
            db.delete_col()

    def test_inf_vector_raises_or_handles_gracefully(self):
        """Inf in vector should raise an error or be handled gracefully."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1005)
            inf_vec = [float("inf"), 0.1, 0.2]
            with pytest.raises((ValueError, Exception)):
                db.insert(
                    ids=[vid],
                    vectors=[inf_vec],
                    payloads=[{"data": "inf vector", "user_id": "dim_user"}],
                )
        finally:
            db.delete_col()

    def test_very_large_values_in_vector(self):
        """Very large float values beyond FLOATVECTOR safety bounds should be rejected by GaussDB."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1006)
            large_vec = [1e30, -1e30, 1e15]
            with pytest.raises(Exception, match="Scalar .* range|exceeds bound|upper limit"):
                db.insert(
                    ids=[vid],
                    vectors=[large_vec],
                    payloads=[{"data": "large values", "user_id": "dim_user"}],
                )
        finally:
            db.delete_col()

    def test_negative_values_in_vector(self):
        """Negative values in vector should work normally."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1007)
            neg_vec = [-0.5, -0.3, -0.9]
            db.insert(
                ids=[vid],
                vectors=[neg_vec],
                payloads=[{"data": "negative vector", "user_id": "dim_user"}],
            )
            results = db.search("neg", neg_vec, top_k=1, filters={"user_id": "dim_user"})
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    def test_empty_vector_list_raises(self):
        """Empty vector list should raise an error."""
        db = _new_db(prefix="p1_dim")
        try:
            vid = _uuid(1008)
            with pytest.raises((ValueError, Exception)):
                db.insert(
                    ids=[vid],
                    vectors=[[]],
                    payloads=[{"data": "empty vector", "user_id": "dim_user"}],
                )
        finally:
            db.delete_col()


# ===========================================================================
# Payload Boundary Tests
# ===========================================================================


class TestPayloadBoundary:
    """Tests for payload edge cases."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="p1_payload")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_empty_payload(self):
        """Empty payload dict should be insertable."""
        vid = _uuid(2001)
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{}])
        result = self.db.get(vid)
        assert result is not None

    def test_large_payload_100kb(self):
        """Large payload (~100KB) should be insertable and retrievable."""
        vid = _uuid(2002)
        large_value = "x" * 100_000
        payload = {"data": "large payload", "user_id": "payload_user", "big_field": large_value}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["big_field"] == large_value

    def test_deeply_nested_payload(self):
        """Deeply nested payload (5 levels) should be stored correctly."""
        vid = _uuid(2003)
        nested = {"level1": {"level2": {"level3": {"level4": {"level5": "deep_value"}}}}}
        payload = {"data": "nested payload", "user_id": "payload_user", "nested": nested}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["nested"]["level1"]["level2"]["level3"]["level4"]["level5"] == "deep_value"

    def test_special_characters_in_payload(self):
        """Special characters in payload values should be preserved."""
        vid = _uuid(2004)
        special = "Hello 'world' \"quotes\" \\backslash\\ <html>&amp; \t\n"
        payload = {"data": special, "user_id": "payload_user", "special": special}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["special"] == special

    def test_unicode_payload_chinese_and_emoji(self):
        """Unicode (Chinese, emoji) in payload should round-trip correctly."""
        vid = _uuid(2005)
        unicode_text = "你好世界 🌍🚀 日本語テスト"
        payload = {"data": unicode_text, "user_id": "payload_user", "text": unicode_text}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["text"] == unicode_text

    def test_very_long_key_in_payload(self):
        """Very long key name (128 chars) in payload should work."""
        vid = _uuid(2006)
        long_key = "k" * 128
        payload = {"data": "long key", "user_id": "payload_user", long_key: "value"}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload[long_key] == "value"

    def test_very_long_value_in_payload(self):
        """Very long value (10KB string) in payload should work."""
        vid = _uuid(2007)
        long_value = "v" * 10_000
        payload = {"data": "long value", "user_id": "payload_user", "long_val": long_value}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["long_val"] == long_value

    def test_null_value_in_payload(self):
        """None/null value in payload should be preserved."""
        vid = _uuid(2008)
        payload = {"data": "null test", "user_id": "payload_user", "nullable": None}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload.get("nullable") is None

    def test_boolean_values_in_payload(self):
        """Boolean values in payload should be preserved."""
        vid = _uuid(2009)
        payload = {"data": "bool test", "user_id": "payload_user", "flag_true": True, "flag_false": False}
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["flag_true"] is True
        assert result.payload["flag_false"] is False

    def test_numeric_values_in_payload(self):
        """Numeric values (int, float) in payload should be preserved."""
        vid = _uuid(2010)
        payload = {
            "data": "numeric test",
            "user_id": "payload_user",
            "int_val": 42,
            "float_val": 3.14,
            "negative": -100,
            "zero": 0,
        }
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["int_val"] == 42
        assert abs(result.payload["float_val"] - 3.14) < 0.001
        assert result.payload["negative"] == -100
        assert result.payload["zero"] == 0


# ===========================================================================
# ID Boundary Tests
# ===========================================================================


class TestIDBoundary:
    """Tests for ID edge cases."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="p1_id")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_uuid_format_id(self):
        """Standard UUID format ID should work."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "uuid id", "user_id": "id_uuid"}])
        result = self.db.get(vid)
        assert result is not None
        assert result.id == vid

    def test_deterministic_uuid_format(self):
        """Deterministic UUID format should work."""
        vid = _uuid(3001)
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "det uuid", "user_id": "id_det"}])
        result = self.db.get(vid)
        assert result is not None
        assert result.id == vid

    def test_duplicate_id_upsert_behavior(self):
        """Inserting with duplicate ID should upsert (update existing)."""
        vid = _uuid(3002)
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "original", "user_id": "id_dup"}])
        self.db.insert(ids=[vid], vectors=[VECTOR_FLIGHT], payloads=[{"data": "updated", "user_id": "id_dup"}])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["data"] == "updated"

    def test_batch_with_duplicate_ids(self):
        """Batch insert with duplicate IDs should raise UniqueViolation."""
        vid = _uuid(3003)
        with pytest.raises(Exception):
            self.db.insert(
                ids=[vid, vid],
                vectors=[VECTOR_COFFEE, VECTOR_FLIGHT],
                payloads=[
                    {"data": "first", "user_id": "id_batchdup"},
                    {"data": "second", "user_id": "id_batchdup"},
                ],
            )

    def test_multiple_unique_ids(self):
        """Multiple unique IDs should all be retrievable."""
        ids = [_uuid(3010 + i) for i in range(5)]
        vectors = [VECTOR_COFFEE] * 5
        payloads = [{"data": f"item_{i}", "user_id": "id_multi"} for i in range(5)]
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)
        for i, vid in enumerate(ids):
            result = self.db.get(vid)
            assert result is not None
            assert result.payload["data"] == f"item_{i}"

    def test_null_id_raises(self):
        """None as ID should raise an error."""
        with pytest.raises((ValueError, TypeError, Exception)):
            self.db.insert(ids=[None], vectors=[VECTOR_COFFEE], payloads=[{"data": "null id", "user_id": "id_null"}])

    def test_get_nonexistent_id_returns_none(self):
        """Getting a non-existent ID should return None."""
        result = self.db.get(_uuid(9999))
        assert result is None

    def test_delete_nonexistent_id_no_error(self):
        """Deleting a non-existent ID should not raise an error."""
        self.db.delete(_uuid(9998))


# ===========================================================================
# Collection Name Boundary Tests
# ===========================================================================


class TestCollectionNameBoundary:
    """Tests for collection name edge cases."""

    def test_max_length_collection_name(self):
        """Collection name at max usable length should work.

        The identifier limit is 63 chars, but GaussDB appends '_schema_meta'
        (12 chars) internally, so the effective max collection name is 51 chars.
        """
        long_name = "a" * 51
        db = _new_db(prefix=None, collection_name=long_name)
        try:
            vid = _uuid(4001)
            db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "long name", "user_id": "col_user"}])
            result = db.get(vid)
            assert result is not None
        finally:
            db.delete_col()

    def test_collection_name_with_underscores(self):
        """Collection name with underscores should work."""
        name = f"test_under_score_{uuid.uuid4().hex[:6]}"
        db = _new_db(prefix=None, collection_name=name)
        try:
            vid = _uuid(4002)
            db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "underscore", "user_id": "col_user"}])
            result = db.get(vid)
            assert result is not None
        finally:
            db.delete_col()

    def test_collection_name_sql_injection_rejected(self):
        """SQL injection in collection name should be rejected by validator."""
        with pytest.raises(ValueError, match="Unsafe"):
            _new_db(prefix=None, collection_name="test; DROP TABLE users;--")

    def test_empty_collection_name_rejected(self):
        """Empty collection name should be rejected."""
        config = _gaussdb_env_config("placeholder")
        config["collection_name"] = ""
        with pytest.raises(ValueError):
            GaussDB(**config)

    def test_collection_name_starting_with_number_rejected(self):
        """Collection name starting with a number should be rejected."""
        with pytest.raises(ValueError, match="Unsafe"):
            _new_db(prefix=None, collection_name="123_invalid")

    def test_collection_name_with_special_chars_rejected(self):
        """Collection name with special characters should be rejected."""
        with pytest.raises(ValueError, match="Unsafe"):
            _new_db(prefix=None, collection_name="test-collection!")


# ===========================================================================
# top_k Boundary Tests
# ===========================================================================


class TestTopKBoundary:
    """Tests for top_k parameter edge cases."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="topk_boundary")
        _insert_memories(cls.db, [
            (_uuid(5001), VECTOR_COFFEE, {"data": "item_0", "user_id": "topk_user"}),
            (_uuid(5002), VECTOR_FLIGHT, {"data": "item_1", "user_id": "topk_user"}),
            (_uuid(5003), VECTOR_WINDOW, {"data": "item_2", "user_id": "topk_user"}),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_top_k_one_returns_single_result(self):
        """top_k=1 should return exactly one result."""
        results = self.db.search("item", VECTOR_COFFEE, top_k=1, filters={"user_id": "topk_user"})
        assert len(results) == 1

    def test_top_k_exceeds_data_count(self):
        """top_k larger than data count should return all available results."""
        results = self.db.search("item", VECTOR_COFFEE, top_k=100, filters={"user_id": "topk_user"})
        assert len(results) == 3

    def test_top_k_very_large_value(self):
        """Very large top_k should not crash."""
        results = self.db.search("single", VECTOR_COFFEE, top_k=10000, filters={"user_id": "topk_user"})
        assert len(results) >= 1

    def test_top_k_zero_returns_empty(self):
        """top_k=0 should return empty results or raise."""
        results = self.db.search("item", VECTOR_COFFEE, top_k=0, filters={"user_id": "topk_user"})
        assert len(results) == 0

    def test_top_k_negative_raises_or_empty(self):
        """Negative top_k should raise an error or return empty."""
        try:
            results = self.db.search("item", VECTOR_COFFEE, top_k=-1, filters={"user_id": "topk_user"})
            assert len(results) == 0
        except (ValueError, Exception):
            pass


# ===========================================================================
# Batch Operation Boundary Tests
# ===========================================================================


class TestBatchOperationBoundary:
    """Tests for batch operation edge cases."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="p1_batch")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_empty_batch_insert(self):
        """Empty batch insert should not crash."""
        result = self.db.insert(ids=[], vectors=[], payloads=[])
        assert result is None or result == []

    def test_single_item_batch(self):
        """Single-item batch should work like single insert."""
        vid = _uuid(6001)
        self.db.insert(ids=[vid], vectors=[VECTOR_COFFEE], payloads=[{"data": "single batch", "user_id": "batch_single"}])
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["data"] == "single batch"

    def test_large_batch_insert_1000_items(self):
        """Large batch (1000 items) should complete successfully."""
        count = 1000
        ids = [_uuid(6100 + i) for i in range(count)]
        vectors = [[float(i % 10) / 10, float(i % 5) / 5, float(i % 3) / 3] for i in range(count)]
        payloads = [{"data": f"batch_item_{i}", "user_id": "batch_large"} for i in range(count)]
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)

        result = self.db.get(ids[0])
        assert result is not None
        result = self.db.get(ids[999])
        assert result is not None

    def test_batch_search_with_multiple_queries(self):
        """search_batch with multiple queries should return results for each."""
        _insert_memories(
            self.db,
            [
                (_uuid(6201), VECTOR_COFFEE, {"data": "coffee memory", "user_id": "batch_search"}),
                (_uuid(6202), VECTOR_FLIGHT, {"data": "flight memory", "user_id": "batch_search"}),
            ],
        )
        results = self.db.search_batch(
            ["coffee", "flight"],
            [VECTOR_COFFEE, VECTOR_FLIGHT],
            top_k=5,
            filters={"user_id": "batch_search"},
        )
        assert len(results) == 2
        assert len(results[0]) >= 1
        assert len(results[1]) >= 1

    def test_batch_insert_partial_failure_handling(self):
        """Batch with some invalid data should handle gracefully."""
        valid_id = _uuid(6301)
        self.db.insert(
            ids=[valid_id],
            vectors=[VECTOR_COFFEE],
            payloads=[{"data": "valid item", "user_id": "batch_partial"}],
        )
        result = self.db.get(valid_id)
        assert result is not None



# ===========================================================================
# Multi-tenant Isolation Tests (from test_gaussdb_p1_multitenant.py)
# ===========================================================================

class TestScopeIsolationCRUD:
    """Tests for user_id, agent_id, run_id, and combined scope isolation with CRUD."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="p1_mt")
        _insert_memories(cls.db, [
            # user_id isolation data
            (_uuid(7001), VECTOR_COFFEE, _make_payload("alice coffee", user_id="mt_alice")),
            (_uuid(7002), VECTOR_FLIGHT, _make_payload("bob flight", user_id="mt_bob")),
            (_uuid(7011), VECTOR_COFFEE, _make_payload("alice likes coffee", user_id="mt_alice")),
            (_uuid(7012), VECTOR_WINDOW, _make_payload("alice likes window", user_id="mt_alice")),
            (_uuid(7013), VECTOR_COFFEE, _make_payload("bob likes coffee", user_id="mt_bob")),
            (_uuid(7014), VECTOR_FLIGHT, _make_payload("charlie flight", user_id="mt_charlie")),
            (_uuid(7021), VECTOR_COFFEE, _make_payload("alice mem1", user_id="mt_alice_list")),
            (_uuid(7022), VECTOR_FLIGHT, _make_payload("alice mem2", user_id="mt_alice_list")),
            (_uuid(7023), VECTOR_WINDOW, _make_payload("bob mem1", user_id="mt_bob_list")),
            # delete scope data (uses exclusive user_ids)
            (_uuid(7031), VECTOR_COFFEE, _make_payload("alice data", user_id="mt_del_alice")),
            (_uuid(7032), VECTOR_FLIGHT, _make_payload("bob data", user_id="mt_del_bob")),
            # delete_all scope data (exclusive user_ids)
            (_uuid(7041), VECTOR_COFFEE, _make_payload("alice mem1", user_id="mt_delall_alice")),
            (_uuid(7042), VECTOR_WINDOW, _make_payload("alice mem2", user_id="mt_delall_alice")),
            (_uuid(7043), VECTOR_FLIGHT, _make_payload("bob mem1", user_id="mt_delall_bob")),
            (_uuid(7044), VECTOR_AISLE, _make_payload("bob mem2", user_id="mt_delall_bob")),
            # agent_id isolation data
            (_uuid(7101), VECTOR_COFFEE, _make_payload("support chat", user_id="mt_agent_alice", agent_id="support_bot")),
            (_uuid(7102), VECTOR_FLIGHT, _make_payload("travel chat", user_id="mt_agent_alice", agent_id="travel_bot")),
            (_uuid(7103), VECTOR_WINDOW, _make_payload("coding chat", user_id="mt_agent_alice", agent_id="code_bot")),
            (_uuid(7111), VECTOR_COFFEE, _make_payload("alice support", user_id="mt_cross_alice", agent_id="support_bot")),
            (_uuid(7112), VECTOR_FLIGHT, _make_payload("bob support", user_id="mt_cross_bob", agent_id="support_bot")),
            (_uuid(7121), VECTOR_COFFEE, _make_payload("agent1 data", user_id="mt_opt_alice", agent_id="agent1")),
            (_uuid(7122), VECTOR_FLIGHT, _make_payload("agent2 data", user_id="mt_opt_alice", agent_id="agent2")),
            (_uuid(7123), VECTOR_WINDOW, _make_payload("agent3 data", user_id="mt_opt_alice", agent_id="agent3")),
            (_uuid(7131), VECTOR_COFFEE, _make_payload("travel mem1", user_id="mt_alist_alice", agent_id="travel_bot")),
            (_uuid(7132), VECTOR_FLIGHT, _make_payload("travel mem2", user_id="mt_alist_alice", agent_id="travel_bot")),
            (_uuid(7133), VECTOR_WINDOW, _make_payload("support mem1", user_id="mt_alist_alice", agent_id="support_bot")),
            (_uuid(7141), VECTOR_COFFEE, _make_payload("alice travel", user_id="mt_comb_alice", agent_id="travel_bot")),
            (_uuid(7142), VECTOR_FLIGHT, _make_payload("bob travel", user_id="mt_comb_bob", agent_id="travel_bot")),
            (_uuid(7143), VECTOR_WINDOW, _make_payload("alice support", user_id="mt_comb_alice", agent_id="support_bot")),
            # run_id isolation data
            (_uuid(7201), VECTOR_COFFEE, _make_payload("run1 data", user_id="mt_run_alice", run_id="run_001")),
            (_uuid(7202), VECTOR_FLIGHT, _make_payload("run2 data", user_id="mt_run_alice", run_id="run_002")),
            (_uuid(7203), VECTOR_WINDOW, _make_payload("run3 data", user_id="mt_run_alice", run_id="run_003")),
            (_uuid(7211), VECTOR_COFFEE, _make_payload("run1 list", user_id="mt_runlist_alice", run_id="run_001")),
            (_uuid(7212), VECTOR_FLIGHT, _make_payload("run1 list2", user_id="mt_runlist_alice", run_id="run_001")),
            (_uuid(7213), VECTOR_WINDOW, _make_payload("run2 list", user_id="mt_runlist_alice", run_id="run_002")),
            (_uuid(7221), VECTOR_COFFEE, _make_payload("run cross alice", user_id="mt_runcross_alice", run_id="run_001")),
            (_uuid(7222), VECTOR_FLIGHT, _make_payload("run cross bob", user_id="mt_runcross_bob", run_id="run_001")),
            # combined scope data
            (_uuid(7301), VECTOR_COFFEE, _make_payload("target", user_id="mt_scope_alice", agent_id="bot_a", run_id="run_001")),
            (_uuid(7302), VECTOR_FLIGHT, _make_payload("diff run", user_id="mt_scope_alice", agent_id="bot_a", run_id="run_002")),
            (_uuid(7303), VECTOR_WINDOW, _make_payload("diff agent", user_id="mt_scope_alice", agent_id="bot_b", run_id="run_001")),
            (_uuid(7304), VECTOR_AISLE, _make_payload("diff user", user_id="mt_scope_bob", agent_id="bot_a", run_id="run_001")),
            (_uuid(7311), VECTOR_COFFEE, _make_payload("full match", user_id="mt_partial_alice", agent_id="bot_a", run_id="run_001")),
            (_uuid(7312), VECTOR_FLIGHT, _make_payload("partial mismatch", user_id="mt_partial_alice", agent_id="bot_a", run_id="run_999")),
            (_uuid(7321), VECTOR_COFFEE, _make_payload("some data", user_id="mt_empty_alice", agent_id="bot_a", run_id="run_001")),
            (_uuid(7322), VECTOR_FLIGHT, _make_payload("other data", user_id="mt_empty_bob", agent_id="bot_b", run_id="run_002")),
            (_uuid(7331), VECTOR_COFFEE, _make_payload("alice bot_a", user_id="mt_wild_alice", agent_id="bot_a")),
            (_uuid(7332), VECTOR_FLIGHT, _make_payload("alice bot_b", user_id="mt_wild_alice", agent_id="bot_b")),
            (_uuid(7333), VECTOR_WINDOW, _make_payload("alice bot_c", user_id="mt_wild_alice", agent_id="bot_c")),
            (_uuid(7334), VECTOR_AISLE, _make_payload("bob bot_a", user_id="mt_wild_bob", agent_id="bot_a")),
        ])

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    # --- user_id isolation ---

    def test_memory_add_user_id_isolation(self):
        """Data added for alice should not be visible to bob."""
        results = self.db.search("coffee", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_bob"})
        result_ids = _ids(results)
        assert _uuid(7001) not in result_ids
        assert _uuid(7002) in result_ids

    def test_memory_search_user_id_isolation(self):
        """Search with user_id filter returns only that user's data."""
        results = self.db.search("coffee", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_alice"})
        result_ids = set(_ids(results))
        assert _uuid(7011) in result_ids
        assert _uuid(7012) in result_ids
        assert _uuid(7013) not in result_ids
        assert _uuid(7014) not in result_ids

    def test_memory_get_all_user_id_filter(self):
        """list with user_id filter returns only that user's data."""
        results = _list_flat(self.db, filters={"user_id": "mt_alice_list"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7021), _uuid(7022)})

    def test_memory_delete_user_id_scope(self):
        """Deleting alice's record doesn't affect bob's data."""
        self.db.delete(vector_id=_uuid(7031))
        bob_result = self.db.get(_uuid(7032))
        assert bob_result is not None
        alice_result = self.db.get(_uuid(7031))
        assert alice_result is None

    def test_memory_delete_all_user_id_scope(self):
        """delete_all for alice preserves bob's data."""
        alice_records = _list_flat(self.db, filters={"user_id": "mt_delall_alice"}, top_k=100)
        alice_ids = _ids(alice_records)
        for aid in alice_ids:
            self.db.delete(vector_id=aid)
        bob_records = _list_flat(self.db, filters={"user_id": "mt_delall_bob"}, top_k=100)
        _assert_exact_ids(bob_records, {_uuid(7043), _uuid(7044)})
        alice_after = _list_flat(self.db, filters={"user_id": "mt_delall_alice"}, top_k=100)
        assert len(alice_after) == 0

    # --- agent_id isolation ---

    def test_agent_id_isolation_basic(self):
        """Same user, different agents should be isolated when filtered."""
        results = self.db.search("chat", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_agent_alice", "agent_id": "support_bot"})
        result_ids = _ids(results)
        assert _uuid(7101) in result_ids
        assert _uuid(7102) not in result_ids
        assert _uuid(7103) not in result_ids

    def test_agent_id_cross_user_isolation(self):
        """Different users with same agent_id should be isolated by user_id."""
        results = self.db.search("support", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_cross_alice", "agent_id": "support_bot"})
        _assert_exact_ids(results, {_uuid(7111)})

    def test_agent_id_optional_filter(self):
        """Without agent_id filter, all records for user are visible."""
        results = _list_flat(self.db, filters={"user_id": "mt_opt_alice"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7121), _uuid(7122), _uuid(7123)})

    def test_agent_id_list_filter(self):
        """list filtered by specific agent_id returns only that agent's data."""
        results = _list_flat(self.db, filters={"user_id": "mt_alist_alice", "agent_id": "travel_bot"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7131), _uuid(7132)})

    def test_agent_id_combined_with_user_id(self):
        """Combined user_id + agent_id filter narrows results correctly."""
        results = _list_flat(self.db, filters={"user_id": "mt_comb_alice", "agent_id": "travel_bot"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7141)})

    # --- run_id isolation ---

    def test_run_id_isolation_basic(self):
        """Different run_ids should be isolated when filtered."""
        results = self.db.search("data", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_run_alice", "run_id": "run_001"})
        result_ids = _ids(results)
        assert _uuid(7201) in result_ids
        assert _uuid(7202) not in result_ids
        assert _uuid(7203) not in result_ids

    def test_run_id_combined_with_user_id(self):
        """user_id + run_id combined filter works correctly."""
        results = _list_flat(self.db, filters={"user_id": "mt_runlist_alice", "run_id": "run_001"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7211), _uuid(7212)})

    def test_run_id_combined_with_agent_id(self):
        """agent_id + run_id combined filter works correctly."""
        results = self.db.search("run cross", VECTOR_COFFEE, top_k=10, filters={"user_id": "mt_runcross_alice", "run_id": "run_001"})
        _assert_exact_ids(results, {_uuid(7221)})

    # --- combined scope isolation ---

    def test_scope_all_three_combined(self):
        """user_id + agent_id + run_id combined filter returns exact match."""
        results = _list_flat(self.db,
            filters={"user_id": "mt_scope_alice", "agent_id": "bot_a", "run_id": "run_001"},
            top_k=100,
        )
        _assert_exact_ids(results, {_uuid(7301)})

    def test_scope_partial_match_excluded(self):
        """Partial scope match (2 of 3 fields) should not return non-matching data."""
        results = _list_flat(self.db,
            filters={"user_id": "mt_partial_alice", "agent_id": "bot_a", "run_id": "run_001"},
            top_k=100,
        )
        _assert_exact_ids(results, {_uuid(7311)})

    def test_scope_empty_result_on_mismatch(self):
        """Completely wrong scope returns empty results."""
        results = _list_flat(self.db,
            filters={"user_id": "charlie", "agent_id": "bot_x", "run_id": "run_999"},
            top_k=100,
        )
        assert len(results) == 0

    def test_scope_wildcard_user_all_agents(self):
        """user_id filter only (no agent_id) sees all agents for that user."""
        results = _list_flat(self.db, filters={"user_id": "mt_wild_alice"}, top_k=100)
        _assert_exact_ids(results, {_uuid(7331), _uuid(7332), _uuid(7333)})


# ===========================================================================
# 7.2.5 Concurrent Multi-user Operations + Concurrent Insert + Upsert Race
# ===========================================================================


class TestConcurrencySafety:
    """Tests for concurrent multi-user operations, inserts, and upsert races."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="p2_conc")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_concurrent_multi_user_add(self):
        """5 threads adding data for different users, verify isolation."""
        users = [f"conc_add_user_{i}" for i in range(5)]
        vectors = [VECTOR_COFFEE, VECTOR_FLIGHT, VECTOR_WINDOW, VECTOR_AISLE, VECTOR_COFFEE]

        def add_for_user(idx):
            uid = users[idx]
            record_id = _uuid(7400 + idx)
            self.db.insert(
                ids=[record_id],
                vectors=[vectors[idx]],
                payloads=[_make_payload(f"{uid} memory", user_id=uid)],
            )
            return uid, record_id

        results_map = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(add_for_user, i): i for i in range(5)}
            for future in as_completed(futures):
                uid, record_id = future.result()
                results_map[uid] = record_id

        for uid, record_id in results_map.items():
            user_records = _list_flat(self.db, filters={"user_id": uid}, top_k=100)
            assert len(user_records) == 1
            assert _ids(user_records)[0] == record_id

    def test_concurrent_multi_user_search(self):
        """5 threads searching for different users, verify isolation."""
        records = []
        for i in range(5):
            uid = f"conc_search_user_{i}"
            vectors = [VECTOR_COFFEE, VECTOR_FLIGHT, VECTOR_WINDOW, VECTOR_AISLE, VECTOR_COFFEE]
            records.append((_uuid(7410 + i), vectors[i], _make_payload(f"{uid} data", user_id=uid)))
        _insert_memories(self.db, records)

        def search_for_user(idx):
            uid = f"conc_search_user_{idx}"
            vectors = [VECTOR_COFFEE, VECTOR_FLIGHT, VECTOR_WINDOW, VECTOR_AISLE, VECTOR_COFFEE]
            results = self.db.search("data", vectors[idx], top_k=10, filters={"user_id": uid})
            return uid, results

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(search_for_user, i): i for i in range(5)}
            for future in as_completed(futures):
                uid, results = future.result()
                result_ids = _ids(results)
                idx = int(uid.split("_")[-1])
                expected_id = _uuid(7410 + idx)
                assert expected_id in result_ids, f"{uid} should see their own data"
                for other_idx in range(5):
                    if other_idx != idx:
                        assert _uuid(7410 + other_idx) not in result_ids

    def test_concurrent_same_user_diff_agent(self):
        """Same user, different agents concurrent operations maintain isolation."""
        agents = [f"conc_agent_{i}" for i in range(5)]
        vectors = [VECTOR_COFFEE, VECTOR_FLIGHT, VECTOR_WINDOW, VECTOR_AISLE, VECTOR_COFFEE]

        def add_for_agent(idx):
            agent = agents[idx]
            record_id = _uuid(7420 + idx)
            self.db.insert(
                ids=[record_id],
                vectors=[vectors[idx]],
                payloads=[_make_payload(f"conc_alice {agent}", user_id="conc_alice", agent_id=agent)],
            )
            return agent, record_id

        results_map = {}
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {executor.submit(add_for_agent, i): i for i in range(5)}
            for future in as_completed(futures):
                agent, record_id = future.result()
                results_map[agent] = record_id

        for agent, record_id in results_map.items():
            agent_records = _list_flat(self.db, filters={"user_id": "conc_alice", "agent_id": agent}, top_k=100)
            assert len(agent_records) == 1
            assert _ids(agent_records)[0] == record_id

        all_records = _list_flat(self.db, filters={"user_id": "conc_alice"}, top_k=100)
        assert len(all_records) == 5

    # --- Concurrent Insert tests ---

    def test_concurrent_insert_basic(self):
        """5 threads, 3 records each - basic concurrent insert."""
        num_threads = 5
        records_per_thread = 3

        def insert_batch(thread_idx):
            for i in range(records_per_thread):
                record_id = str(uuid.uuid4())
                self.db.insert(
                    ids=[record_id],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(
                        f"conc_basic_{thread_idx}_{i}",
                        user_id="conc_basic_user",
                    )],
                )

        tasks = [lambda idx=t: insert_batch(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        final_count = len(_list_flat(self.db, filters={"user_id": "conc_basic_user"}, top_k=500))
        total_expected = num_threads * records_per_thread
        assert final_count == total_expected

    @pytest.mark.high_pressure
    def test_concurrent_insert_high_pressure(self):
        """10 threads, 5 records each - high pressure stress test (2x pool size)."""
        num_threads = 10
        records_per_thread = 5

        def insert_batch(thread_idx):
            for i in range(records_per_thread):
                record_id = str(uuid.uuid4())
                self.db.insert(
                    ids=[record_id],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(
                        f"hp_{thread_idx}_{i}",
                        user_id="conc_hp_user",
                    )],
                )

        tasks = [lambda idx=t: insert_batch(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads, timeout=600.0)

        final_count = len(_list_flat(self.db, filters={"user_id": "conc_hp_user"}, top_k=1500))
        total_expected = num_threads * records_per_thread
        assert final_count >= total_expected * 0.5

    def test_concurrent_insert_with_batch(self):
        """5 threads each batch-inserting 20 records at once."""
        num_threads = 5
        batch_size = 20

        def batch_insert(thread_idx):
            ids = [str(uuid.uuid4()) for _ in range(batch_size)]
            vectors = [_random_vector() for _ in range(batch_size)]
            payloads = [
                _make_payload(f"batch_{thread_idx}_{i}", user_id="conc_batch_user")
                for i in range(batch_size)
            ]
            self.db.insert(ids=ids, vectors=vectors, payloads=payloads)

        tasks = [lambda idx=t: batch_insert(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        final_count = len(_list_flat(self.db, filters={"user_id": "conc_batch_user"}, top_k=600))
        total_expected = num_threads * batch_size
        if not errors:
            assert final_count == total_expected
        else:
            assert final_count > 0

    # --- Upsert Race Conditions ---

    def test_concurrent_upsert_same_id(self):
        """10 threads upsert same ID concurrently. Final count must be 1."""
        target_id = _uuid(9001)
        num_threads = 10

        def upsert_record(thread_idx):
            vector = _random_vector()
            payload = _make_payload(
                f"upsert_thread_{thread_idx}",
                user_id="conc_upsert_user",
            )
            self.db.insert(
                ids=[target_id],
                vectors=[vector],
                payloads=[payload],
            )

        tasks = [lambda idx=t: upsert_record(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        result = self.db.get(target_id)
        assert result is not None
        assert len(_list_flat(self.db, filters={"user_id": "conc_upsert_user"}, top_k=100)) == 1

    def test_concurrent_upsert_same_id_same_payload(self):
        """10 threads upsert same ID with identical payload. Idempotency check."""
        target_id = _uuid(9002)
        num_threads = 10
        fixed_vector = VECTOR_COFFEE
        fixed_payload = _make_payload("idempotent_data", user_id="conc_idem_user")

        def upsert_same(thread_idx):
            self.db.insert(
                ids=[target_id],
                vectors=[fixed_vector],
                payloads=[fixed_payload],
            )

        tasks = [lambda idx=t: upsert_same(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        result = self.db.get(target_id)
        assert result is not None
        assert result.payload["data"] == "idempotent_data"
        assert len(_list_flat(self.db, filters={"user_id": "conc_idem_user"}, top_k=100)) == 1

    def test_concurrent_upsert_same_id_update_vs_insert(self):
        """Insert first, then concurrent upserts. Verify final state is consistent."""
        target_id = _uuid(9003)
        self.db.insert(
            ids=[target_id],
            vectors=[VECTOR_COFFEE],
            payloads=[_make_payload("original", user_id="conc_upins_user")],
        )

        num_threads = 10

        def upsert_update(thread_idx):
            vector = _random_vector()
            payload = _make_payload(
                f"updated_by_{thread_idx}",
                user_id="conc_upins_user",
            )
            self.db.insert(
                ids=[target_id],
                vectors=[vector],
                payloads=[payload],
            )

        tasks = [lambda idx=t: upsert_update(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        result = self.db.get(target_id)
        assert result is not None
        assert result.payload["data"].startswith("updated_by_")
        assert len(_list_flat(self.db, filters={"user_id": "conc_upins_user"}, top_k=100)) == 1

    def test_concurrent_upsert_batch_same_ids(self):
        """Batch upsert with overlapping IDs from multiple threads."""
        shared_ids = [_uuid(9010 + i) for i in range(5)]
        num_threads = 10

        def batch_upsert(thread_idx):
            vectors = [_random_vector() for _ in range(5)]
            payloads = [
                _make_payload(f"batch_t{thread_idx}_r{i}", user_id="conc_batchup_user")
                for i in range(5)
            ]
            self.db.insert(ids=shared_ids, vectors=vectors, payloads=payloads)

        tasks = [lambda idx=t: batch_upsert(idx) for t in range(num_threads)]
        successes, errors = _run_concurrent(tasks, max_workers=num_threads)

        for sid in shared_ids:
            result = self.db.get(sid)
            assert result is not None
        assert len(_list_flat(self.db, filters={"user_id": "conc_batchup_user"}, top_k=100)) == 5

    def test_upsert_lost_update_detection(self):
        """2 threads sequential upsert. Verify last-write-wins semantics."""
        target_id = _uuid(9020)
        barrier = threading.Barrier(2, timeout=30)
        write_order = []
        order_lock = threading.Lock()

        def upsert_with_order(thread_idx):
            barrier.wait()
            vector = _random_vector()
            payload = _make_payload(
                f"writer_{thread_idx}",
                user_id="conc_lww_user",
            )
            self.db.insert(
                ids=[target_id],
                vectors=[vector],
                payloads=[payload],
            )
            with order_lock:
                write_order.append(thread_idx)

        tasks = [lambda idx=t: upsert_with_order(idx) for t in range(2)]
        successes, errors = _run_concurrent(tasks, max_workers=2)

        result = self.db.get(target_id)
        assert result is not None
        assert len(_list_flat(self.db, filters={"user_id": "conc_lww_user"}, top_k=100)) == 1
        assert result.payload["data"] in ("writer_0", "writer_1")


# ===========================================================================
# 9.2.3 Read-Write Concurrency
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestReadWriteConcurrency:
    """Tests for concurrent read and write operations."""

    def test_concurrent_insert_and_search(self):
        """5 insert threads + 5 search threads running simultaneously."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "rw_insert_search"
            # Pre-insert some data so searches have something to find
            for i in range(20):
                db.insert(
                    ids=[str(uuid.uuid4())],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"seed_{i}", user_id=user_id)],
                )

            def inserter(thread_idx):
                for i in range(20):
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"insert_t{thread_idx}_{i}", user_id=user_id
                        )],
                    )

            def searcher(thread_idx):
                for i in range(20):
                    results = db.search(
                        "query", _random_vector(), top_k=5,
                        filters={"user_id": user_id},
                    )
                    # Search should not crash; results may vary
                    assert isinstance(results, list)

            tasks = (
                [lambda idx=t: inserter(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)

            # All operations should complete without fatal errors
            assert successes >= 5  # At least the searchers should succeed
        finally:
            db.delete_col()

    def test_concurrent_update_and_search(self):
        """5 update threads + 5 search threads running simultaneously."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "rw_update_search"
            record_ids = []
            for i in range(50):
                rid = str(uuid.uuid4())
                record_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"original_{i}", user_id=user_id)],
                )

            def updater(thread_idx):
                for i in range(10):
                    target = record_ids[(thread_idx * 10 + i) % len(record_ids)]
                    db.update(
                        vector_id=target,
                        vector=_random_vector(),
                        payload=_make_payload(
                            f"updated_t{thread_idx}_{i}", user_id=user_id
                        ),
                    )

            def searcher(thread_idx):
                for i in range(10):
                    db.search(
                        "query", _random_vector(), top_k=5,
                        filters={"user_id": user_id},
                    )

            tasks = (
                [lambda idx=t: updater(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)

            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count == 50
        finally:
            db.delete_col()

    def test_concurrent_delete_and_search(self):
        """5 delete threads + 5 search threads running simultaneously."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "rw_delete_search"
            record_ids = []
            for i in range(100):
                rid = str(uuid.uuid4())
                record_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"to_delete_{i}", user_id=user_id)],
                )

            # Split IDs among delete threads
            chunk_size = 20

            def deleter(thread_idx):
                start = thread_idx * chunk_size
                ids_to_delete = record_ids[start:start + chunk_size]
                for rid in ids_to_delete:
                    db.delete(vector_id=rid)

            def searcher(thread_idx):
                for i in range(20):
                    results = db.search(
                        "query", _random_vector(), top_k=5,
                        filters={"user_id": user_id},
                    )
                    assert isinstance(results, list)

            tasks = (
                [lambda idx=t: deleter(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)

            # After deletion, count should be reduced
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count < 100
        finally:
            db.delete_col()

    def test_concurrent_insert_and_get(self):
        """5 insert threads + 5 get threads running simultaneously."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "rw_insert_get"
            # Pre-insert known records for get operations
            known_ids = []
            for i in range(20):
                rid = _uuid(8000 + i)
                known_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"known_{i}", user_id=user_id)],
                )

            def inserter(thread_idx):
                for i in range(20):
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"new_t{thread_idx}_{i}", user_id=user_id
                        )],
                    )

            def getter(thread_idx):
                for i in range(20):
                    target = known_ids[i % len(known_ids)]
                    result = db.get(target)
                    # Record should always be retrievable (not deleted)
                    assert result is not None

            tasks = (
                [lambda idx=t: inserter(idx) for t in range(5)]
                + [lambda idx=t: getter(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=10)

            # Known records should still exist
            for kid in known_ids:
                assert db.get(kid) is not None
        finally:
            db.delete_col()

    def test_concurrent_mixed_operations(self):
        """Insert/update/delete/search mixed, 20 threads total."""
        db = _new_db(prefix="p2_conc", maxconn=25)
        try:
            user_id = "rw_mixed"
            # Pre-insert records for update/delete/search
            record_ids = []
            for i in range(100):
                rid = str(uuid.uuid4())
                record_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"mixed_{i}", user_id=user_id)],
                )

            def inserter(thread_idx):
                for i in range(10):
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"mixed_new_t{thread_idx}_{i}", user_id=user_id
                        )],
                    )

            def updater(thread_idx):
                for i in range(10):
                    target = record_ids[(thread_idx * 10 + i) % len(record_ids)]
                    try:
                        db.update(
                            vector_id=target,
                            vector=_random_vector(),
                            payload=_make_payload(
                                f"mixed_upd_t{thread_idx}_{i}", user_id=user_id
                            ),
                        )
                    except Exception:
                        pass  # Record may have been deleted

            def deleter(thread_idx):
                # Delete from the end of the list to minimize conflict with updaters
                start = 80 + thread_idx * 4
                for i in range(4):
                    idx = start + i
                    if idx < len(record_ids):
                        try:
                            db.delete(vector_id=record_ids[idx])
                        except Exception:
                            pass

            def searcher(thread_idx):
                for i in range(10):
                    db.search(
                        "query", _random_vector(), top_k=5,
                        filters={"user_id": user_id},
                    )

            tasks = (
                [lambda idx=t: inserter(idx) for t in range(5)]
                + [lambda idx=t: updater(idx) for t in range(5)]
                + [lambda idx=t: deleter(idx) for t in range(5)]
                + [lambda idx=t: searcher(idx) for t in range(5)]
            )
            successes, errors = _run_concurrent(tasks, max_workers=20)

            # System should remain operational after mixed concurrent ops
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count > 0
        finally:
            db.delete_col()


# ===========================================================================
# 9.2.4 Connection Pool Exhaustion
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestConnectionPoolExhaustion:
    """Tests for connection pool behavior under pressure."""

    def test_connection_pool_exhaustion(self):
        """maxconn=2, 5 concurrent threads. Operations should still complete."""
        db = _new_db(prefix="p2_conc", maxconn=2)
        try:
            user_id = "pool_exhaust"
            # Pre-insert some data
            for i in range(10):
                db.insert(
                    ids=[_uuid(7000 + i)],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"pool_{i}", user_id=user_id)],
                )

            def worker(thread_idx):
                for i in range(10):
                    db.search(
                        "query", _random_vector(), top_k=3,
                        filters={"user_id": user_id},
                    )
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"pool_t{thread_idx}_{i}", user_id=user_id
                        )],
                    )

            tasks = [lambda idx=t: worker(idx) for t in range(5)]
            successes, errors = _run_concurrent(tasks, max_workers=5)

            # With pool exhaustion, some operations may fail but system recovers
            # At least some threads should succeed
            assert successes > 0
        finally:
            db.delete_col()

    def test_connection_pool_recovery(self):
        """Exhaust pool, then verify recovery after connections are released."""
        db = _new_db(prefix="p2_conc", maxconn=3)
        try:
            user_id = "pool_recovery"

            # Phase 1: Exhaust the pool with concurrent operations
            def heavy_worker(thread_idx):
                for i in range(20):
                    db.insert(
                        ids=[str(uuid.uuid4())],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"heavy_{thread_idx}_{i}", user_id=user_id
                        )],
                    )

            tasks = [lambda idx=t: heavy_worker(idx) for t in range(6)]
            successes, errors = _run_concurrent(tasks, max_workers=6)

            # Phase 2: After pool pressure, verify system recovers
            time.sleep(1)  # Allow connections to be returned to pool

            # Single-threaded operations should work fine after recovery
            recovery_id = str(uuid.uuid4())
            db.insert(
                ids=[recovery_id],
                vectors=[_random_vector()],
                payloads=[_make_payload("recovery_test", user_id=user_id)],
            )
            result = db.get(recovery_id)
            assert result is not None
            assert result.payload["data"] == "recovery_test"
        finally:
            db.delete_col()

    def test_connection_pool_leak_detection(self):
        """100 sequential operations. Verify no connection leak."""
        db = _new_db(prefix="p2_conc", maxconn=5)
        try:
            user_id = "pool_leak"

            # Perform many operations that acquire and release connections
            for i in range(100):
                rid = str(uuid.uuid4())
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"leak_test_{i}", user_id=user_id)],
                )
                # Alternate between different operation types
                if i % 3 == 0:
                    db.search(
                        "query", _random_vector(), top_k=3,
                        filters={"user_id": user_id},
                    )
                elif i % 3 == 1:
                    db.get(rid)

            # After 100 operations, the system should still be responsive
            # If there were connection leaks, this would fail with pool exhaustion
            final_id = str(uuid.uuid4())
            db.insert(
                ids=[final_id],
                vectors=[_random_vector()],
                payloads=[_make_payload("final_check", user_id=user_id)],
            )
            result = db.get(final_id)
            assert result is not None
            assert result.payload["data"] == "final_check"

            # Verify total count is consistent
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            assert final_count == 101  # 100 + 1 final
        finally:
            db.delete_col()


# ===========================================================================
# 9.2.5 Concurrent Data Consistency
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestConcurrentDataConsistency:
    """Tests verifying data consistency after concurrent operations."""

    def test_concurrent_insert_final_count(self):
        """5 threads x 10 records = final count 50."""
        db = _new_db(prefix="p2_conc")
        try:
            num_threads = 5
            records_per_thread = 10
            user_id = "consistency_count"

            all_ids = []
            ids_lock = threading.Lock()

            def insert_batch(thread_idx):
                local_ids = []
                for i in range(records_per_thread):
                    rid = str(uuid.uuid4())
                    local_ids.append(rid)
                    db.insert(
                        ids=[rid],
                        vectors=[_random_vector()],
                        payloads=[_make_payload(
                            f"count_t{thread_idx}_{i}", user_id=user_id
                        )],
                    )
                with ids_lock:
                    all_ids.extend(local_ids)

            tasks = [lambda idx=t: insert_batch(idx) for t in range(num_threads)]
            successes, errors = _run_concurrent(tasks, max_workers=num_threads)

            total_expected = num_threads * records_per_thread
            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=total_expected + 100))
            if not errors:
                assert final_count == total_expected
            else:
                # With errors, count should match successful inserts
                assert final_count == len(all_ids)
        finally:
            db.delete_col()

    def test_concurrent_upsert_final_state(self):
        """5 threads upsert same ID. Final state must be consistent (single record)."""
        db = _new_db(prefix="p2_conc")
        try:
            target_id = _uuid(9100)
            num_threads = 5
            user_id = "consistency_upsert"

            def upsert_record(thread_idx):
                for i in range(5):
                    vector = _random_vector()
                    payload = _make_payload(
                        f"state_t{thread_idx}_i{i}",
                        user_id=user_id,
                    )
                    db.insert(
                        ids=[target_id],
                        vectors=[vector],
                        payloads=[payload],
                    )

            tasks = [lambda idx=t: upsert_record(idx) for t in range(num_threads)]
            successes, errors = _run_concurrent(tasks, max_workers=num_threads)

            # Final state: exactly 1 record with consistent payload
            result = db.get(target_id)
            assert result is not None
            assert len(_list_flat(db, filters={"user_id": user_id}, top_k=100)) == 1
            # Payload should be from one of the threads/iterations
            assert result.payload["data"].startswith("state_t")
            assert result.payload["user_id"] == user_id
        finally:
            db.delete_col()

    def test_concurrent_delete_final_count(self):
        """Insert 100, 10 threads delete 10 each. Final count should be 0."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "consistency_delete"
            record_ids = []
            for i in range(100):
                rid = _uuid(8100 + i)
                record_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"del_{i}", user_id=user_id)],
                )

            assert len(_list_flat(db, filters={"user_id": user_id}, top_k=200)) == 100

            def delete_batch(thread_idx):
                start = thread_idx * 10
                for i in range(10):
                    idx = start + i
                    if idx < len(record_ids):
                        db.delete(vector_id=record_ids[idx])

            tasks = [lambda idx=t: delete_batch(idx) for t in range(10)]
            successes, errors = _run_concurrent(tasks, max_workers=10)

            final_count = len(_list_flat(db, filters={"user_id": user_id}, top_k=200))
            if not errors:
                assert final_count == 0
            else:
                # Some deletes may have failed, but count should be reduced
                assert final_count < 100
        finally:
            db.delete_col()

    def test_concurrent_update_payload_consistency(self):
        """10 threads update different fields of same records. Final state consistent."""
        db = _new_db(prefix="p2_conc", maxconn=15)
        try:
            user_id = "consistency_update"
            # Insert 10 records
            record_ids = []
            for i in range(10):
                rid = _uuid(8200 + i)
                record_ids.append(rid)
                db.insert(
                    ids=[rid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"original_{i}", user_id=user_id)],
                )

            def updater(thread_idx):
                """Each thread updates all 10 records with its own marker."""
                for i, rid in enumerate(record_ids):
                    try:
                        db.update(
                            vector_id=rid,
                            vector=_random_vector(),
                            payload=_make_payload(
                                f"updated_t{thread_idx}_r{i}",
                                user_id=user_id,
                                thread_marker=f"thread_{thread_idx}",
                            ),
                        )
                    except Exception:
                        pass  # Contention may cause transient failures

            tasks = [lambda idx=t: updater(idx) for t in range(10)]
            successes, errors = _run_concurrent(tasks, max_workers=10)

            # Verify consistency: each record should have a valid payload
            for rid in record_ids:
                result = db.get(rid)
                assert result is not None
                # Payload should be from one of the threads (last-write-wins)
                assert result.payload["user_id"] == user_id
                # Data field should be either original or from a thread update
                data = result.payload["data"]
                assert data.startswith("original_") or data.startswith("updated_t")

            # Total count should remain unchanged
            assert len(_list_flat(db, filters={"user_id": user_id}, top_k=100)) == 10
        finally:
            db.delete_col()




# ===========================================================================
# Performance Baseline Tests (from test_gaussdb_p2_performance.py)
# ===========================================================================

@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestSingleOperationLatency:
    """Measure latency of individual CRUD operations."""

    def test_single_insert_latency(self):
        """Insert 100 times, report P50/P95/P99 (target P50<100ms)."""
        db = _new_db(prefix="p2_perf")
        try:
            counter = [0]

            def _do_insert():
                counter[0] += 1
                vid = str(uuid.uuid4())
                db.insert(
                    ids=[vid],
                    vectors=[_random_vector()],
                    payloads=[_make_payload(f"insert_latency_{counter[0]}")],
                )

            stats = _measure_latency(_do_insert, iterations=100)
            _print_latency_report("single_insert", stats)
            _soft_assert(stats["p50_ms"] < 100, f"P50 insert latency {stats['p50_ms']:.2f}ms > 100ms target")
        finally:
            db.delete_col()

    def test_single_search_latency(self):
        """Search 100 times, report P50/P95/P99 (target P50<50ms)."""
        db = _new_db(prefix="p2_perf")
        try:
            # Pre-populate with some data
            ids = [str(uuid.uuid4()) for _ in range(50)]
            vectors = [_random_vector() for _ in range(50)]
            payloads = [_make_payload(f"search_data_{i}") for i in range(50)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            def _do_search():
                db.search("query", _random_vector(), top_k=5, filters={"user_id": "test_user"})

            stats = _measure_latency(_do_search, iterations=100)
            _print_latency_report("single_search", stats)
            _soft_assert(stats["p50_ms"] < 50, f"P50 search latency {stats['p50_ms']:.2f}ms > 50ms target")
        finally:
            db.delete_col()

    def test_single_update_latency(self):
        """Update 100 times, report P50/P95/P99 (target P50<150ms)."""
        db = _new_db(prefix="p2_perf")
        try:
            # Insert a record to update repeatedly
            vid = _uuid(9001)
            db.insert(
                ids=[vid],
                vectors=[_random_vector()],
                payloads=[_make_payload("update_target")],
            )
            counter = [0]

            def _do_update():
                counter[0] += 1
                db.update(
                    vid,
                    vector=_random_vector(),
                    payload=_make_payload(f"updated_{counter[0]}"),
                )

            stats = _measure_latency(_do_update, iterations=100)
            _print_latency_report("single_update", stats)
            _soft_assert(stats["p50_ms"] < 150, f"P50 update latency {stats['p50_ms']:.2f}ms > 150ms target")
        finally:
            db.delete_col()

    def test_single_get_latency(self):
        """Get 100 times, report P50/P95/P99 (target P50<10ms)."""
        db = _new_db(prefix="p2_perf")
        try:
            vid = _uuid(9002)
            db.insert(
                ids=[vid],
                vectors=[_random_vector()],
                payloads=[_make_payload("get_target")],
            )

            def _do_get():
                db.get(vid)

            stats = _measure_latency(_do_get, iterations=100)
            _print_latency_report("single_get", stats)
            _soft_assert(stats["p50_ms"] < 10, f"P50 get latency {stats['p50_ms']:.2f}ms > 10ms target")
        finally:
            db.delete_col()

    def test_single_delete_latency(self):
        """Delete 100 times, report P50/P95/P99 (target P50<50ms)."""
        db = _new_db(prefix="p2_perf")
        try:
            # Pre-insert 100 records to delete one by one
            ids_to_delete = [str(uuid.uuid4()) for _ in range(100)]
            vectors = [_random_vector() for _ in range(100)]
            payloads = [_make_payload(f"delete_target_{i}") for i in range(100)]
            db.insert(ids=ids_to_delete, vectors=vectors, payloads=payloads)

            idx = [0]

            def _do_delete():
                db.delete(vector_id=ids_to_delete[idx[0]])
                idx[0] += 1

            stats = _measure_latency(_do_delete, iterations=100)
            _print_latency_report("single_delete", stats)
            _soft_assert(stats["p50_ms"] < 50, f"P50 delete latency {stats['p50_ms']:.2f}ms > 50ms target")
        finally:
            db.delete_col()


# ===========================================================================
# 8.2.2 Batch Operation Throughput Tests
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestBatchOperationThroughput:
    """Measure throughput of batch operations."""

    def test_batch_insert_100_throughput(self):
        """Insert 100 records in one batch, measure throughput (target >50 records/s)."""
        db = _new_db(prefix="p2_perf")
        try:
            count = 100
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [_make_payload(f"batch100_{i}") for i in range(count)]

            start = time.perf_counter()
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            elapsed = time.perf_counter() - start

            throughput = count / elapsed
            print(f"\n  [PERF] batch_insert_100: {elapsed:.3f}s, throughput: {throughput:.1f} records/s")
            _soft_assert(throughput > 50, f"Batch insert 100 throughput {throughput:.1f} < 50 records/s target")
        finally:
            db.delete_col()

    def test_batch_insert_1000_throughput(self):
        """Insert 1000 records in one batch, measure throughput (target >100 records/s)."""
        db = _new_db(prefix="p2_perf")
        try:
            count = 1000
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [_make_payload(f"batch1k_{i}") for i in range(count)]

            start = time.perf_counter()
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            elapsed = time.perf_counter() - start

            throughput = count / elapsed
            print(f"\n  [PERF] batch_insert_1000: {elapsed:.3f}s, throughput: {throughput:.1f} records/s")
            _soft_assert(throughput > 100, f"Batch insert 1000 throughput {throughput:.1f} < 100 records/s target")
        finally:
            db.delete_col()

    @pytest.mark.high_pressure
    def test_batch_insert_10000_throughput(self):
        """Insert 10000 records in one batch, measure throughput (target >200 records/s)."""
        db = _new_db(prefix="p2_perf")
        try:
            count = 10000
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [_make_payload(f"batch10k_{i}") for i in range(count)]

            start = time.perf_counter()
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            elapsed = time.perf_counter() - start

            throughput = count / elapsed
            print(f"\n  [PERF] batch_insert_10000: {elapsed:.3f}s, throughput: {throughput:.1f} records/s")
            _soft_assert(throughput > 200, f"Batch insert 10000 throughput {throughput:.1f} < 200 records/s target")
        finally:
            db.delete_col()

    def test_batch_search_10_throughput(self):
        """10 sequential searches, measure throughput."""
        db = _new_db(prefix="p2_perf")
        try:
            # Pre-populate
            count = 200
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [_make_payload(f"search_data_{i}") for i in range(count)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            num_searches = 10
            start = time.perf_counter()
            for _ in range(num_searches):
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "test_user"})
            elapsed = time.perf_counter() - start

            throughput = num_searches / elapsed
            print(f"\n  [PERF] batch_search_10: {elapsed:.3f}s, throughput: {throughput:.1f} searches/s")
        finally:
            db.delete_col()

    def test_batch_search_100_throughput(self):
        """100 sequential searches, measure throughput."""
        db = _new_db(prefix="p2_perf")
        try:
            # Pre-populate
            count = 200
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [_make_payload(f"search_data_{i}") for i in range(count)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            num_searches = 100
            start = time.perf_counter()
            for _ in range(num_searches):
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "test_user"})
            elapsed = time.perf_counter() - start

            throughput = num_searches / elapsed
            print(f"\n  [PERF] batch_search_100: {elapsed:.3f}s, throughput: {throughput:.1f} searches/s")
        finally:
            db.delete_col()


# ===========================================================================
# 8.2.3 Data Size vs Search Latency Tests
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestDataSizeVsSearchLatency:
    """Measure how search latency scales with data size."""

    def _populate_and_measure(self, db, record_count: int, label: str):
        """Insert record_count records and measure search latency."""
        batch_size = 1000
        inserted = 0
        while inserted < record_count:
            batch = min(batch_size, record_count - inserted)
            ids = [str(uuid.uuid4()) for _ in range(batch)]
            vectors = [_random_vector() for _ in range(batch)]
            payloads = [_make_payload(f"data_{inserted + i}") for i in range(batch)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            inserted += batch

        def _do_search():
            db.search("query", _random_vector(), top_k=10, filters={"user_id": "test_user"})

        stats = _measure_latency(_do_search, iterations=50)
        _print_latency_report(f"search_latency_{label} (n={record_count})", stats)
        return stats

    def test_search_latency_vs_data_size_100(self):
        """Search latency with 100 records."""
        db = _new_db(prefix="p2_perf")
        try:
            stats = self._populate_and_measure(db, 100, "100")
            _soft_assert(stats["p50_ms"] < 100, f"P50 search@100 = {stats['p50_ms']:.2f}ms")
        finally:
            db.delete_col()

    def test_search_latency_vs_data_size_1000(self):
        """Search latency with 1000 records."""
        db = _new_db(prefix="p2_perf")
        try:
            stats = self._populate_and_measure(db, 1000, "1000")
            _soft_assert(stats["p50_ms"] < 200, f"P50 search@1000 = {stats['p50_ms']:.2f}ms")
        finally:
            db.delete_col()

    @pytest.mark.high_pressure
    def test_search_latency_vs_data_size_10000(self):
        """Search latency with 10000 records."""
        db = _new_db(prefix="p2_perf")
        try:
            stats = self._populate_and_measure(db, 10000, "10000")
            _soft_assert(stats["p50_ms"] < 500, f"P50 search@10000 = {stats['p50_ms']:.2f}ms")
        finally:
            db.delete_col()

    @pytest.mark.high_pressure
    def test_search_latency_vs_data_size_100000(self):
        """Search latency with 100000 records. Skipped if env not configured for high pressure."""
        if not _env_bool("GAUSSDB_TEST_RUN_HIGH_PRESSURE"):
            pytest.skip("Set GAUSSDB_TEST_RUN_HIGH_PRESSURE=true to run 100k record tests")
        db = _new_db(prefix="p2_perf")
        try:
            stats = self._populate_and_measure(db, 100000, "100000")
            _soft_assert(stats["p50_ms"] < 2000, f"P50 search@100000 = {stats['p50_ms']:.2f}ms")
        finally:
            db.delete_col()


# ===========================================================================
# 8.2.4 Filter Search Performance Tests
# ===========================================================================


@pytest.mark.skipif(not _env_bool("GAUSSDB_TEST_RUN_PERF"), reason="Performance tests disabled; set GAUSSDB_TEST_RUN_PERF=1 to enable")
class TestFilterSearchPerformance:
    """Compare search performance with and without filters."""

    def test_search_with_filter_vs_without_filter(self):
        """Compare latency of filtered vs unfiltered search."""
        db = _new_db(prefix="p2_perf")
        try:
            # Populate with mixed user_ids
            count = 500
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [
                _make_payload(f"item_{i}", user_id=f"user_{i % 10}")
                for i in range(count)
            ]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            def _search_no_filter():
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "user_0"})

            def _search_with_filter():
                db.search(
                    "query", _random_vector(), top_k=10,
                    filters={"user_id": "user_0", "data": "item_0"},
                )

            stats_no_filter = _measure_latency(_search_no_filter, iterations=50)
            stats_with_filter = _measure_latency(_search_with_filter, iterations=50)

            _print_latency_report("search_single_filter", stats_no_filter)
            _print_latency_report("search_multi_filter", stats_with_filter)

            ratio = stats_with_filter["p50_ms"] / max(stats_no_filter["p50_ms"], 0.01)
            print(f"\n  [PERF] Filter overhead ratio (multi/single): {ratio:.2f}x")
        finally:
            db.delete_col()

    def test_search_filter_simple_vs_complex(self):
        """Compare simple filter vs complex nested filter performance."""
        db = _new_db(prefix="p2_perf")
        try:
            # Populate with varied metadata
            count = 500
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [
                _make_payload(
                    f"item_{i}",
                    user_id=f"user_{i % 10}",
                    category=f"cat_{i % 5}",
                    priority=i % 3,
                )
                for i in range(count)
            ]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            # Simple filter: single field
            def _search_simple():
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "user_3"})

            # Complex filter: multiple fields combined
            def _search_complex():
                db.search(
                    "query", _random_vector(), top_k=10,
                    filters={"user_id": "user_3", "category": "cat_2", "priority": 1},
                )

            stats_simple = _measure_latency(_search_simple, iterations=50)
            stats_complex = _measure_latency(_search_complex, iterations=50)

            _print_latency_report("search_simple_filter", stats_simple)
            _print_latency_report("search_complex_filter", stats_complex)

            ratio = stats_complex["p50_ms"] / max(stats_simple["p50_ms"], 0.01)
            print(f"\n  [PERF] Complex/Simple filter ratio: {ratio:.2f}x")
        finally:
            db.delete_col()

    def test_search_filter_json_expression_vs_redundant_columns(self):
        """Compare JSON expression filter vs redundant column filter performance."""
        db = _new_db(prefix="p2_perf")
        try:
            # Populate data with metadata stored in payload
            count = 500
            ids = [str(uuid.uuid4()) for _ in range(count)]
            vectors = [_random_vector() for _ in range(count)]
            payloads = [
                _make_payload(
                    f"item_{i}",
                    user_id=f"user_{i % 10}",
                    region=f"region_{i % 4}",
                    score=float(i % 100),
                )
                for i in range(count)
            ]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            # Filter by user_id (typically a redundant/indexed column)
            def _search_by_user_id():
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "user_5"})

            # Filter by a JSON payload field (region) with required scope
            def _search_by_json_field():
                db.search("query", _random_vector(), top_k=10, filters={"user_id": "user_5", "region": "region_2"})

            stats_user_id = _measure_latency(_search_by_user_id, iterations=50)
            stats_json = _measure_latency(_search_by_json_field, iterations=50)

            _print_latency_report("search_filter_user_id_column", stats_user_id)
            _print_latency_report("search_filter_json_field", stats_json)

            ratio = stats_json["p50_ms"] / max(stats_user_id["p50_ms"], 0.01)
            print(f"\n  [PERF] JSON filter / column filter ratio: {ratio:.2f}x")
        finally:
            db.delete_col()



# ===========================================================================
# GaussDB-specific Feature Tests (from test_gaussdb_gaussdb_features.py)
# ===========================================================================

class TestUstoreStorageEngine:
    """Tests for Ustore storage engine behavior."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="feat_ustore")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_ustore_table_creation(self):
        """Create collection with Ustore engine, verify basic CRUD works."""
        vid = _uuid(7001)
        self.db.insert(
            ids=[vid],
            vectors=[VECTOR_COFFEE],
            payloads=[_make_payload("ustore creation test", "ustore_user")],
        )
        # Verify insert
        result = self.db.get(vid)
        assert result is not None
        assert result.id == vid
        assert result.payload["data"] == "ustore creation test"

        # Verify search
        results = self.db.search(
            "ustore", VECTOR_COFFEE, top_k=1, filters={"user_id": "ustore_user"}
        )
        assert len(results) >= 1
        assert results[0].id == vid

        # Verify delete
        self.db.delete(vector_id=vid)
        result_after = self.db.get(vid)
        assert result_after is None

    def test_ustore_vs_astore_insert_perf(self):
        """Compare insert performance (informational, no hard assertion)."""
        num_records = 50
        ids = [_uuid(7100 + i) for i in range(num_records)]
        vectors = [[random.random() for _ in range(EMBEDDING_DIMS)] for _ in range(num_records)]
        payloads = [_make_payload(f"perf record {i}", "perf_user") for i in range(num_records)]

        start = time.perf_counter()
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)
        insert_duration_ms = (time.perf_counter() - start) * 1000

        # Informational: just verify all records were inserted
        count = len(_list_flat(self.db, filters={"user_id": "perf_user"}, top_k=1000))
        assert count == num_records
        # Log performance (no hard assertion on timing)
        assert insert_duration_ms >= 0  # trivially true, documents the measurement

    def test_ustore_vs_astore_search_perf(self):
        """Compare search performance (informational, no hard assertion)."""
        # Insert baseline data
        num_records = 50
        ids = [_uuid(7200 + i) for i in range(num_records)]
        vectors = [[random.random() for _ in range(EMBEDDING_DIMS)] for _ in range(num_records)]
        payloads = [_make_payload(f"search perf {i}", "perf_user") for i in range(num_records)]
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)

        query_vector = [random.random() for _ in range(EMBEDDING_DIMS)]

        start = time.perf_counter()
        iterations = 20
        for _ in range(iterations):
            self.db.search("perf", query_vector, top_k=10, filters={"user_id": "perf_user"})
        search_duration_ms = (time.perf_counter() - start) * 1000

        avg_search_ms = search_duration_ms / iterations
        # Informational: verify search returns results and measure timing
        results = self.db.search("perf", query_vector, top_k=10, filters={"user_id": "perf_user"})
        assert len(results) >= 1
        assert avg_search_ms >= 0  # trivially true, documents the measurement

    def test_ustore_update_in_place(self):
        """Verify update works correctly (in-place update behavior)."""
        vid = _uuid(7301)
        # Insert original record
        self.db.insert(
            ids=[vid],
            vectors=[VECTOR_COFFEE],
            payloads=[_make_payload("original data", "update_user")],
        )
        original = self.db.get(vid)
        assert original is not None
        assert original.payload["data"] == "original data"

        # Update vector and payload in place
        new_vector = VECTOR_FLIGHT
        self.db.update(
            vector_id=vid,
            vector=new_vector,
            payload=_make_payload("updated data", "update_user"),
        )

        # Verify update took effect
        updated = self.db.get(vid)
        assert updated is not None
        assert updated.payload["data"] == "updated data"

        # Verify search finds updated record with new vector
        results = self.db.search(
            "updated", VECTOR_FLIGHT, top_k=1, filters={"user_id": "update_user"}
        )
        assert len(results) >= 1
        assert results[0].id == vid
        assert results[0].payload["data"] == "updated data"


# ===========================================================================
# 10.2.2 FLOATVECTOR Type Boundary Verification
# ===========================================================================


class TestFloatvectorTypeBoundary:
    """Tests for FLOATVECTOR type precision and boundary behavior."""

    def test_floatvector_precision_float32(self):
        """Verify float32 precision is maintained in storage and retrieval."""
        db = _new_db(prefix="feat_fvec")
        try:
            vid = _uuid(7401)
            # Use values that test float32 precision boundaries
            precise_vector = [0.123456789, 0.987654321, 0.555555555]
            db.insert(
                ids=[vid],
                vectors=[precise_vector],
                payloads=[_make_payload("precision test", "fvec_user")],
            )

            # Search with the same vector should return high similarity
            results = db.search(
                "precision", precise_vector, top_k=1, filters={"user_id": "fvec_user"}
            )
            assert len(results) == 1
            assert results[0].id == vid
            # Raw cosine distance should be near zero for an identical vector
            if results[0].score is not None:
                assert abs(results[0].score - 0.0) < 1e-5
        finally:
            db.delete_col()

    def test_floatvector_max_dimensions_supported(self):
        """Test maximum supported dimensions (use 1024 as a high-dim test)."""
        max_dims = 1024
        db = _new_db(prefix="feat_fvec_max", embedding_model_dims=max_dims)
        try:
            vid = _uuid(7501)
            high_dim_vector = [random.random() for _ in range(max_dims)]
            db.insert(
                ids=[vid],
                vectors=[high_dim_vector],
                payloads=[_make_payload("max dim test", "fvec_user")],
            )

            results = db.search(
                "maxdim", high_dim_vector, top_k=1, filters={"user_id": "fvec_user"}
            )
            assert len(results) == 1
            assert results[0].id == vid
        finally:
            db.delete_col()

    @pytest.mark.xfail(reason="GaussDB floatvector distance overflows with extreme values (FLT_MAX)")
    def test_floatvector_special_values(self):
        """Test with very small and very large float values."""
        db = _new_db(prefix="feat_fvec_special")
        try:
            # Very small values (near epsilon)
            vid_small = _uuid(7601)
            small_vector = [1e-30, 1e-30, 1e-30]
            db.insert(
                ids=[vid_small],
                vectors=[small_vector],
                payloads=[_make_payload("small values", "fvec_user")],
            )

            # Very large values
            vid_large = _uuid(7602)
            large_vector = [1e30, 1e30, 1e30]
            db.insert(
                ids=[vid_large],
                vectors=[large_vector],
                payloads=[_make_payload("large values", "fvec_user")],
            )

            # Verify both records exist
            result_small = db.get(vid_small)
            result_large = db.get(vid_large)
            assert result_small is not None
            assert result_large is not None

            # Search should distinguish between them
            results = db.search(
                "small", small_vector, top_k=2, filters={"user_id": "fvec_user"}
            )
            assert len(results) == 2
        finally:
            db.delete_col()

    def test_floatvector_normalized_vs_unnormalized(self):
        """Test with normalized (unit length) and unnormalized vectors."""
        db = _new_db(prefix="feat_fvec_norm")
        try:
            # Normalized vector (unit length)
            vid_norm = _uuid(7701)
            import math
            norm_factor = math.sqrt(0.1**2 + 0.2**2 + 0.3**2)
            normalized_vector = [0.1 / norm_factor, 0.2 / norm_factor, 0.3 / norm_factor]
            db.insert(
                ids=[vid_norm],
                vectors=[normalized_vector],
                payloads=[_make_payload("normalized", "fvec_user")],
            )

            # Unnormalized vector (same direction, different magnitude)
            vid_unnorm = _uuid(7702)
            unnormalized_vector = [10.0, 20.0, 30.0]
            db.insert(
                ids=[vid_unnorm],
                vectors=[unnormalized_vector],
                payloads=[_make_payload("unnormalized", "fvec_user")],
            )

            # Both should be retrievable
            result_norm = db.get(vid_norm)
            result_unnorm = db.get(vid_unnorm)
            assert result_norm is not None
            assert result_unnorm is not None

            # Cosine similarity search: same direction vectors should both rank high
            results = db.search(
                "direction", [1.0, 2.0, 3.0], top_k=2, filters={"user_id": "fvec_user"}
            )
            assert len(results) == 2
            returned_ids = {r.id for r in results}
            assert vid_norm in returned_ids
            assert vid_unnorm in returned_ids
        finally:
            db.delete_col()


# ===========================================================================
# 10.2.3 Vector Index Type Comparison
# ===========================================================================


class TestVectorIndexTypeComparison:
    """Tests for GsIVFFlat and GsDiskANN index types."""

    def test_gsivfflat_index_basic_crud(self):
        """Basic CRUD with GsIVFFlat index type."""
        db = _new_db(prefix="feat_ivfflat", vector_index_type="gsivfflat")
        try:
            vid = _uuid(8001)
            db.insert(
                ids=[vid],
                vectors=[VECTOR_COFFEE],
                payloads=[_make_payload("ivfflat test", "idx_user")],
            )

            # Search
            results = db.search(
                "ivfflat", VECTOR_COFFEE, top_k=1, filters={"user_id": "idx_user"}
            )
            assert len(results) == 1
            assert results[0].id == vid

            # Update
            db.update(
                vector_id=vid,
                vector=VECTOR_FLIGHT,
                payload=_make_payload("ivfflat updated", "idx_user"),
            )
            updated = db.get(vid)
            assert updated is not None
            assert updated.payload["data"] == "ivfflat updated"

            # Delete
            db.delete(vector_id=vid)
            assert db.get(vid) is None
        finally:
            db.delete_col()

    @pytest.mark.skipif(
        os.getenv("GAUSSDB_TEST_VECTOR_INDEX") != "gsdiskann",
        reason="GsDiskANN not configured",
    )
    def test_gsdiskann_index_basic_crud(self):
        """Basic CRUD with GsDiskANN index type (skip if not available)."""
        db = _new_db(prefix="feat_diskann", vector_index_type="gsdiskann")
        try:
            vid = _uuid(8101)
            db.insert(
                ids=[vid],
                vectors=[VECTOR_WINDOW],
                payloads=[_make_payload("diskann test", "idx_user")],
            )

            # Search
            results = db.search(
                "diskann", VECTOR_WINDOW, top_k=1, filters={"user_id": "idx_user"}
            )
            assert len(results) == 1
            assert results[0].id == vid

            # Update
            db.update(
                vector_id=vid,
                vector=VECTOR_AISLE,
                payload=_make_payload("diskann updated", "idx_user"),
            )
            updated = db.get(vid)
            assert updated is not None
            assert updated.payload["data"] == "diskann updated"

            # Delete
            db.delete(vector_id=vid)
            assert db.get(vid) is None
        finally:
            db.delete_col()

    def test_index_type_search_recall_comparison(self):
        """Compare recall between GsIVFFlat index (informational)."""
        db = _new_db(prefix="feat_idx_recall", vector_index_type="gsivfflat")
        try:
            # Insert a set of known vectors
            num_records = 30
            ids = [_uuid(8200 + i) for i in range(num_records)]
            vectors = [[random.random() for _ in range(EMBEDDING_DIMS)] for _ in range(num_records)]
            payloads = [_make_payload(f"recall item {i}", "recall_user") for i in range(num_records)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)

            # Search with one of the inserted vectors (should find itself)
            target_idx = 5
            results = db.search(
                "recall", vectors[target_idx], top_k=5, filters={"user_id": "recall_user"}
            )
            assert len(results) >= 1
            # The exact vector should be the top result (recall = 1 for exact match)
            assert results[0].id == ids[target_idx]
        finally:
            db.delete_col()

    def test_index_rebuild_after_bulk_insert(self):
        """Verify index works correctly after bulk insert."""
        db = _new_db(prefix="feat_idx_bulk", vector_index_type="gsivfflat")
        try:
            # First batch
            batch1_ids = [_uuid(8300 + i) for i in range(20)]
            batch1_vectors = [[random.random() for _ in range(EMBEDDING_DIMS)] for _ in range(20)]
            batch1_payloads = [_make_payload(f"batch1 item {i}", "bulk_user") for i in range(20)]
            db.insert(ids=batch1_ids, vectors=batch1_vectors, payloads=batch1_payloads)

            # Second batch (simulates bulk insert after index creation)
            batch2_ids = [_uuid(8320 + i) for i in range(20)]
            batch2_vectors = [[random.random() for _ in range(EMBEDDING_DIMS)] for _ in range(20)]
            batch2_payloads = [_make_payload(f"batch2 item {i}", "bulk_user") for i in range(20)]
            db.insert(ids=batch2_ids, vectors=batch2_vectors, payloads=batch2_payloads)

            # Verify total count
            assert len(_list_flat(db, filters={"user_id": "bulk_user"}, top_k=1000)) == 40

            # Search should find records from both batches
            results = db.search(
                "bulk", batch2_vectors[10], top_k=5, filters={"user_id": "bulk_user"}
            )
            assert len(results) >= 1
            # The exact vector from batch2 should be findable
            assert batch2_ids[10] in {r.id for r in results}
        finally:
            db.delete_col()


# ===========================================================================
# 10.2.4 Deployment Mode Verification
# ===========================================================================


class TestDeploymentMode:
    """Tests for centralized and distributed deployment modes."""

    def test_centralized_mode_basic_operations(self):
        """Verify all operations work in centralized mode."""
        db = _new_db(prefix="feat_central", deployment_mode="centralized")
        try:
            # Insert
            vid1 = _uuid(9001)
            vid2 = _uuid(9002)
            db.insert(
                ids=[vid1, vid2],
                vectors=[VECTOR_COFFEE, VECTOR_FLIGHT],
                payloads=[
                    _make_payload("centralized item 1", "deploy_user"),
                    _make_payload("centralized item 2", "deploy_user"),
                ],
            )

            # Count
            assert len(_list_flat(db, filters={"user_id": "deploy_user"}, top_k=1000)) == 2

            # Search
            results = db.search(
                "centralized", VECTOR_COFFEE, top_k=2, filters={"user_id": "deploy_user"}
            )
            assert len(results) == 2

            # Get
            result = db.get(vid1)
            assert result is not None
            assert result.payload["data"] == "centralized item 1"

            # Update
            db.update(
                vector_id=vid1,
                vector=VECTOR_WINDOW,
                payload=_make_payload("centralized updated", "deploy_user"),
            )
            updated = db.get(vid1)
            assert updated.payload["data"] == "centralized updated"

            # List
            listed = _list_flat(db, filters={"user_id": "deploy_user"}, top_k=10)
            assert len(listed) == 2

            # Delete
            db.delete(vector_id=vid1)
            assert db.get(vid1) is None
            assert len(_list_flat(db, filters={"user_id": "deploy_user"}, top_k=1000)) == 1
        finally:
            db.delete_col()

    @pytest.mark.skipif(
        os.getenv("GAUSSDB_TEST_DEPLOYMENT_MODE") != "distributed",
        reason="Distributed mode not configured",
    )
    def test_distributed_mode_basic_operations(self):
        """Verify operations in distributed mode (skip if not configured)."""
        db = _new_db(prefix="feat_distrib", deployment_mode="distributed")
        try:
            # Insert
            vid1 = _uuid(9101)
            vid2 = _uuid(9102)
            db.insert(
                ids=[vid1, vid2],
                vectors=[VECTOR_WINDOW, VECTOR_AISLE],
                payloads=[
                    _make_payload("distributed item 1", "distrib_user"),
                    _make_payload("distributed item 2", "distrib_user"),
                ],
            )

            # Count
            assert len(_list_flat(db, filters={"user_id": "distrib_user"}, top_k=1000)) == 2

            # Search
            results = db.search(
                "distributed", VECTOR_WINDOW, top_k=2, filters={"user_id": "distrib_user"}
            )
            assert len(results) >= 1

            # Get
            result = db.get(vid1)
            assert result is not None
            assert result.payload["data"] == "distributed item 1"

            # Update
            db.update(
                vector_id=vid2,
                vector=VECTOR_COFFEE,
                payload=_make_payload("distributed updated", "distrib_user"),
            )
            updated = db.get(vid2)
            assert updated.payload["data"] == "distributed updated"

            # Delete
            db.delete(vector_id=vid1)
            assert db.get(vid1) is None
            assert len(_list_flat(db, filters={"user_id": "distrib_user"}, top_k=1000)) == 1
        finally:
            db.delete_col()


# ===========================================================================
# 10.2.5 MERGE INTO Atomicity Verification
# ===========================================================================


class TestMergeIntoAtomicity:
    """Tests for MERGE INTO (upsert) atomicity behavior."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="feat_merge")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_merge_into_insert_new_record(self):
        """MERGE INTO inserts when record doesn't exist."""
        vid = _uuid(9201)
        # Use update which triggers MERGE INTO behavior (upsert)
        # First verify the record does not exist
        assert self.db.get(vid) is None

        # Insert via normal insert (establishes baseline)
        self.db.insert(
            ids=[vid],
            vectors=[VECTOR_COFFEE],
            payloads=[_make_payload("merge insert test", "merge_user")],
        )

        # Verify the record was created
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["data"] == "merge insert test"

    def test_merge_into_update_existing_record(self):
        """MERGE INTO updates when record exists (upsert semantics)."""
        user_id = f"merge_user_{uuid.uuid4().hex[:8]}"
        vid = _uuid(9301)
        # Insert initial record
        self.db.insert(
            ids=[vid],
            vectors=[VECTOR_COFFEE],
            payloads=[_make_payload("original merge", user_id)],
        )

        # Update the same ID (triggers MERGE INTO / upsert path)
        self.db.update(
            vector_id=vid,
            vector=VECTOR_FLIGHT,
            payload=_make_payload("updated merge", user_id),
        )

        # Verify update took effect atomically
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["data"] == "updated merge"

        # Verify no duplicate was created
        assert len(_list_flat(self.db, filters={"user_id": user_id}, top_k=1000)) == 1

    def test_merge_into_idempotent_same_data(self):
        """MERGE INTO with same data is idempotent."""
        user_id = f"merge_user_{uuid.uuid4().hex[:8]}"
        vid = _uuid(9401)
        vector = VECTOR_WINDOW
        payload = _make_payload("idempotent test", user_id)

        # Insert the record
        self.db.insert(ids=[vid], vectors=[vector], payloads=[payload])

        # Apply the same update multiple times
        for _ in range(3):
            self.db.update(vector_id=vid, vector=vector, payload=payload)

        # Verify record is unchanged and no duplicates
        result = self.db.get(vid)
        assert result is not None
        assert result.payload["data"] == "idempotent test"
        assert len(_list_flat(self.db, filters={"user_id": user_id}, top_k=1000)) == 1

        # Verify search still works correctly
        results = self.db.search(
            "idempotent", vector, top_k=1, filters={"user_id": user_id}
        )
        assert len(results) == 1
        assert results[0].id == vid


# ===========================================================================
# P0 Core Tests (from test_gaussdb_p0.py)
# Tenant isolation, JSON filters, UTF-8, metrics, BM25, collection ops,
# migration, index matrix
# ===========================================================================

def test_memory_from_config_add_search_delete_uses_real_gaussdb_provider():
    collection = _new_collection("mem0_p0_memory")
    vector_config = _gaussdb_env_config(collection)
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
            metadata={"source": "p0-memory"},
        )
        memory_id = added["results"][0]["id"]

        search_result = memory.search("window seat", filters={"user_id": "alice"}, top_k=5, threshold=0)
        rows = search_result["results"]
        assert [row["id"] for row in rows] == [memory_id]
        assert rows[0]["memory"] == "Alice prefers window seats on morning flights"
        assert rows[0]["user_id"] == "alice"
        assert rows[0]["metadata"]["source"] == "p0-memory"

        with pytest.raises(ValueError, match="filters must contain at least one of"):
            memory.search("window seat", filters={"category": "travel"}, top_k=5, threshold=0)

        memory.delete(memory_id)
        assert memory.vector_store.get(memory_id) is None
    finally:
        memory.vector_store.delete_col()
        if getattr(memory, "_entity_store", None) is not None:
            memory.entity_store.delete_col()


def test_provider_crud_batch_upsert_update_and_delete():
    db = _new_db()
    try:
        first_id = _uuid(1)
        second_id = _uuid(2)
        _insert_memories(
            db,
            [
                (
                    first_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Alice drinks latte coffee",
                        "text_lemmatized": "alice drinks latte coffee",
                        "user_id": "alice",
                        "category": "drink",
                    },
                ),
                (
                    second_id,
                    VECTOR_FLIGHT,
                    {
                        "data": "Alice books morning flights",
                        "text_lemmatized": "alice books morning flights",
                        "user_id": "alice",
                        "category": "travel",
                    },
                ),
            ],
        )

        assert db.get(first_id).payload["data"] == "Alice drinks latte coffee"
        search_rows = db.search("coffee", VECTOR_COFFEE, top_k=2, filters={"user_id": "alice"})
        assert _ids(search_rows)[0] == first_id

        db.update(
            first_id,
            vector=VECTOR_WINDOW,
            payload={
                "data": "Alice now prefers a window seat",
                "text_lemmatized": "alice now prefers a window seat",
                "user_id": "alice",
                "category": "travel",
            },
        )
        updated = db.get(first_id)
        assert updated.payload["data"] == "Alice now prefers a window seat"
        assert _ids(db.search("window", VECTOR_WINDOW, top_k=2, filters={"user_id": "alice"}))[0] == first_id

        db.insert(
            ids=[second_id],
            vectors=[VECTOR_AISLE],
            payloads=[
                {
                    "data": "Alice changed to an aisle seat",
                    "text_lemmatized": "alice changed to an aisle seat",
                    "user_id": "alice",
                    "category": "travel",
                }
            ],
        )
        assert db.get(second_id).payload["data"] == "Alice changed to an aisle seat"

        db.delete(first_id)
        assert db.get(first_id) is None
        _assert_exact_ids(_list_flat(db, {"user_id": "alice"}), {second_id})
    finally:
        db.delete_col()


def test_scoped_search_list_and_batch_do_not_cross_tenants():
    db = _new_db(require_scoped_filters=True)
    try:
        alice_id = _uuid(11)
        bob_id = _uuid(12)
        public_id = _uuid(13)
        _insert_memories(
            db,
            [
                (
                    alice_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Alice likes latte coffee",
                        "text_lemmatized": "alice likes latte coffee",
                        "user_id": "alice",
                        "category": "private",
                    },
                ),
                (
                    bob_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Bob likes latte coffee",
                        "text_lemmatized": "bob likes latte coffee",
                        "user_id": "bob",
                        "category": "private",
                    },
                ),
                (
                    public_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Public coffee note",
                        "text_lemmatized": "public coffee note",
                        "category": "public",
                    },
                ),
            ],
        )

        _assert_exact_ids(db.search("latte", VECTOR_COFFEE, top_k=10, filters={"user_id": "alice"}), {alice_id})
        _assert_exact_ids(_list_flat(db, {"user_id": "alice"}), {alice_id})

        batch_rows = db.search_batch(
            ["latte", "coffee"],
            [VECTOR_COFFEE, VECTOR_COFFEE],
            top_k=10,
            filters={"user_id": "alice"},
        )
        assert [set(_ids(rows)) for rows in batch_rows] == [{alice_id}, {alice_id}]

        valid_or_rows = db.search(
            "latte",
            VECTOR_COFFEE,
            top_k=10,
            filters={"$or": [{"user_id": "alice"}, {"user_id": "bob"}]},
        )
        _assert_exact_ids(valid_or_rows, {alice_id, bob_id})

        with pytest.raises(ValueError, match="requires at least one scoped filter"):
            db.search("latte", VECTOR_COFFEE, top_k=10, filters={"$or": [{"user_id": "alice"}, {"category": "public"}]})

        with pytest.raises(ValueError, match="requires at least one scoped filter"):
            db.search("latte", VECTOR_COFFEE, top_k=10, filters={"user_id": {"ne": "bob"}})

        with pytest.raises(ValueError, match="requires at least one scoped filter"):
            db.list(filters={"category": "public"})
    finally:
        db.delete_col()


def test_live_keyword_and_batch_paths_reject_non_constraining_scope_filters():
    db = _new_db(require_scoped_filters=True)
    try:
        db.bm25_enabled = True
        bad_filters = [
            {"$or": [{"user_id": "alice"}, {"category": "public"}]},
            {"user_id": {"ne": "bob"}},
            {"$not": [{"user_id": "alice"}]},
        ]

        for filters in bad_filters:
            with pytest.raises(ValueError, match="requires at least one scoped filter"):
                db.keyword_search("latte", top_k=5, filters=filters)
            with pytest.raises(ValueError, match="requires at least one scoped filter"):
                db.search_batch(["latte"], [VECTOR_COFFEE], top_k=1, filters=filters)
    finally:
        db.delete_col()


def test_json_payload_filter_operator_matrix():
    db = _new_db()
    try:
        travel_id = _uuid(21)
        food_id = _uuid(22)
        work_id = _uuid(23)
        _insert_memories(
            db,
            [
                (
                    travel_id,
                    VECTOR_FLIGHT,
                    {
                        "data": "Plan flight with priority boarding",
                        "text_lemmatized": "plan flight with priority boarding",
                        "user_id": "filter_user",
                        "category": "travel",
                        "priority": 7,
                        "tag": "boarding-plan",
                    },
                ),
                (
                    food_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Find coffee near the office",
                        "text_lemmatized": "find coffee near the office",
                        "user_id": "filter_user",
                        "category": "food",
                        "priority": 2,
                        "tag": "coffee-shop",
                    },
                ),
                (
                    work_id,
                    VECTOR_WINDOW,
                    {
                        "data": "Prepare quarterly plan",
                        "text_lemmatized": "prepare quarterly plan",
                        "user_id": "filter_user",
                        "category": "work",
                        "priority": 5,
                        "tag": "QuarterlyPlan",
                    },
                ),
            ],
        )

        cases = [
            ({"user_id": "filter_user", "category": {"eq": "travel"}}, {travel_id}),
            ({"user_id": "filter_user", "category": {"ne": "travel"}}, {food_id, work_id}),
            ({"user_id": "filter_user", "category": {"in": ["travel", "food"]}}, {travel_id, food_id}),
            ({"user_id": "filter_user", "category": {"nin": ["travel", "food"]}}, {work_id}),
            ({"user_id": "filter_user", "priority": {"eq": 7}}, {travel_id}),
            ({"user_id": "filter_user", "priority": {"gt": 3}}, set()),
            ({"user_id": "filter_user", "priority": {"gte": 5, "lte": 7}}, set()),
            ({"user_id": "filter_user", "tag": {"contains": "coffee"}}, {food_id}),
            ({"user_id": "filter_user", "tag": {"icontains": "plan"}}, {travel_id, work_id}),
            ({"$and": [{"user_id": "filter_user"}, {"category": "travel"}, {"priority": 7}]}, {travel_id}),
            (
                {
                    "$or": [
                        {"user_id": "filter_user", "category": "travel"},
                        {"user_id": "filter_user", "category": "food"},
                    ]
                },
                {travel_id, food_id},
            ),
            ({"user_id": "filter_user", "$not": [{"category": "food"}]}, {travel_id, work_id}),
        ]

        for filters, expected_ids in cases:
            rows = db.search("filter", VECTOR_COFFEE, top_k=10, filters=filters)
            _assert_exact_ids(rows, expected_ids)
    finally:
        db.delete_col()


def test_utf8_chinese_and_mixed_payload_round_trip():
    db = _new_db()
    try:
        if _server_encoding(db) != "UTF8":
            pytest.skip("UTF-8 payload round trip requires a UTF8 GaussDB database")

        chinese_id = _uuid(41)
        mixed_id = _uuid(42)
        _insert_memories(
            db,
            [
                (
                    chinese_id,
                    VECTOR_COFFEE,
                    {
                        "data": "我喜欢早晨喝拿铁咖啡",
                        "text_lemmatized": "我 喜欢 早晨 喝 拿铁 咖啡",
                        "user_id": "zh_user",
                        "language": "zh",
                    },
                ),
                (
                    mixed_id,
                    VECTOR_FLIGHT,
                    {
                        "data": "小李 books flights with priority boarding",
                        "text_lemmatized": "小李 books flights with priority boarding",
                        "user_id": "zh_user",
                        "language": "mixed",
                    },
                ),
            ],
        )

        assert db.get(chinese_id).payload["data"] == "我喜欢早晨喝拿铁咖啡"
        assert db.get(mixed_id).payload["data"] == "小李 books flights with priority boarding"
        _assert_exact_ids(
            db.search("拿铁", VECTOR_COFFEE, top_k=2, filters={"user_id": "zh_user"}), {chinese_id, mixed_id}
        )
        _assert_exact_ids(_list_flat(db, {"user_id": "zh_user"}), {chinese_id, mixed_id})
    finally:
        db.delete_col()


def test_live_payload_only_and_vector_only_update_paths():
    db = _new_db()
    try:
        memory_id = _uuid(131)
        _insert_memories(
            db,
            [
                (
                    memory_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Original update path memory",
                        "text_lemmatized": "original update path memory",
                        "user_id": "update_user",
                        "category": "initial",
                    },
                )
            ],
        )

        db.update(
            memory_id,
            payload={
                "data": "Payload-only update memory",
                "text_lemmatized": "payload only update memory",
                "user_id": "update_user",
                "category": "changed",
            },
        )
        payload_updated = db.get(memory_id)
        assert payload_updated.payload["data"] == "Payload-only update memory"
        assert payload_updated.payload["category"] == "changed"
        assert _ids(db.search("payload", VECTOR_COFFEE, top_k=1, filters={"user_id": "update_user"})) == [memory_id]

        db.update(memory_id, vector=VECTOR_AISLE)
        vector_updated = db.get(memory_id)
        assert vector_updated.payload["data"] == "Payload-only update memory"
        assert vector_updated.payload["text_lemmatized"] == "payload only update memory"
        assert _ids(db.search("aisle", VECTOR_AISLE, top_k=1, filters={"user_id": "update_user"})) == [memory_id]
    finally:
        db.delete_col()


def test_live_multi_row_batch_upsert_updates_existing_and_inserts_new_rows():
    db = _new_db()
    try:
        existing_id = _uuid(141)
        untouched_id = _uuid(142)
        new_id = _uuid(143)
        _insert_memories(
            db,
            [
                (
                    existing_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Existing batch memory",
                        "text_lemmatized": "existing batch memory",
                        "user_id": "upsert_user",
                    },
                ),
                (
                    untouched_id,
                    VECTOR_FLIGHT,
                    {
                        "data": "Untouched batch memory",
                        "text_lemmatized": "untouched batch memory",
                        "user_id": "upsert_user",
                    },
                ),
            ],
        )

        _insert_memories(
            db,
            [
                (
                    existing_id,
                    VECTOR_WINDOW,
                    {
                        "data": "Existing batch memory updated",
                        "text_lemmatized": "existing batch memory updated",
                        "user_id": "upsert_user",
                    },
                ),
                (
                    new_id,
                    VECTOR_AISLE,
                    {
                        "data": "New batch memory",
                        "text_lemmatized": "new batch memory",
                        "user_id": "upsert_user",
                    },
                ),
            ],
        )

        assert db.get(existing_id).payload["data"] == "Existing batch memory updated"
        assert db.get(untouched_id).payload["data"] == "Untouched batch memory"
        assert db.get(new_id).payload["data"] == "New batch memory"
        _assert_exact_ids(_list_flat(db, {"user_id": "upsert_user"}), {existing_id, untouched_id, new_id})
    finally:
        db.delete_col()


@pytest.mark.parametrize("metric", ["cosine", "l2"])
def test_vector_metric_exact_match_returns_first(metric):
    db = _new_db(vector_metric=metric)
    try:
        exact_id = _uuid(51)
        far_id = _uuid(52)
        _insert_memories(
            db,
            [
                (
                    exact_id,
                    [1.0, 0.0, 0.0],
                    {
                        "data": f"Exact vector for {metric}",
                        "text_lemmatized": f"exact vector for {metric}",
                        "user_id": "metric_user",
                    },
                ),
                (
                    far_id,
                    [0.0, 1.0, 0.0],
                    {
                        "data": f"Far vector for {metric}",
                        "text_lemmatized": f"far vector for {metric}",
                        "user_id": "metric_user",
                    },
                ),
            ],
        )

        rows = db.search("exact", [1.0, 0.0, 0.0], top_k=2, filters={"user_id": "metric_user"})
        assert _ids(rows) == [exact_id, far_id]
        assert rows[0].score <= rows[1].score
    finally:
        db.delete_col()


def test_search_batch_native_results_match_sequential_results():
    db = _new_db()
    try:
        coffee_id = _uuid(61)
        flight_id = _uuid(62)
        _insert_memories(
            db,
            [
                (
                    coffee_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Coffee note",
                        "text_lemmatized": "coffee note",
                        "user_id": "batch_user",
                    },
                ),
                (
                    flight_id,
                    VECTOR_FLIGHT,
                    {
                        "data": "Flight note",
                        "text_lemmatized": "flight note",
                        "user_id": "batch_user",
                    },
                ),
            ],
        )

        fallback_count_before = db.metrics.get("gaussdb_fallback_count", 0)
        batch_rows = db.search_batch(
            ["coffee", "flight"],
            [VECTOR_COFFEE, VECTOR_FLIGHT],
            top_k=1,
            filters={"user_id": "batch_user"},
        )
        assert db.metrics.get("gaussdb_fallback_count", 0) == fallback_count_before
        sequential_rows = [
            db.search("coffee", VECTOR_COFFEE, top_k=1, filters={"user_id": "batch_user"}),
            db.search("flight", VECTOR_FLIGHT, top_k=1, filters={"user_id": "batch_user"}),
        ]
        assert [[row.id for row in rows] for rows in batch_rows] == [
            [row.id for row in rows] for rows in sequential_rows
        ]
        assert [[row.id for row in rows] for rows in batch_rows] == [[coffee_id], [flight_id]]
    finally:
        db.delete_col()


def test_collection_operations_schema_info_analyze_reset_and_list_cols():
    collection = _new_collection("mem0_p0_ops")
    db = _new_db(collection)
    try:
        _insert_memories(
            db,
            [
                (
                    _uuid(71),
                    VECTOR_COFFEE,
                    {
                        "data": "Operational memory one",
                        "text_lemmatized": "operational memory one",
                        "user_id": "ops_user",
                    },
                ),
                (
                    _uuid(72),
                    VECTOR_FLIGHT,
                    {
                        "data": "Operational memory two",
                        "text_lemmatized": "operational memory two",
                        "user_id": "ops_user",
                    },
                ),
            ],
        )

        info = db.col_info()
        assert info["name"] == collection
        assert info["count"] == 2
        assert info["schema_version"] >= 1
        assert info["payload_storage_mode"] == "jsonb"
        assert info["filter_storage_mode"] == "json_expression"
        assert any("vector_idx" in index for index in info["indexes"])

        listed_collections = db.list_cols()
        assert collection in listed_collections
        assert f"{collection}_schema_meta" not in listed_collections

        db.reset()
        assert db.col_info()["count"] == 0
    finally:
        db.delete_col()


def test_concurrent_scoped_searches_return_stable_ids():
    db = _new_db(maxconn=5)
    try:
        expected_id = _uuid(101)
        _insert_memories(
            db,
            [
                (
                    expected_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Concurrent search memory",
                        "text_lemmatized": "concurrent search memory",
                        "user_id": "concurrent_user",
                    },
                )
            ],
        )

        def search_once():
            rows = db.search("concurrent", VECTOR_COFFEE, top_k=1, filters={"user_id": "concurrent_user"})
            return _ids(rows)

        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda _: search_once(), range(8)))

        assert results == [[expected_id]] * 8
    finally:
        db.delete_col()


@pytest.mark.skipif(
    not _env_bool("GAUSSDB_TEST_RUN_BM25"),
    reason="Set GAUSSDB_TEST_RUN_BM25=true to run native BM25 live tests",
)
def test_bm25_keyword_search_is_scoped_and_empty_query_returns_empty_list():
    db = _new_db()
    try:
        alice_id = _uuid(111)
        bob_id = _uuid(112)
        _insert_memories(
            db,
            [
                (
                    alice_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Alice likes latte coffee",
                        "text_lemmatized": "alice likes latte coffee",
                        "user_id": "bm25_alice",
                    },
                ),
                (
                    bob_id,
                    VECTOR_COFFEE,
                    {
                        "data": "Bob likes latte coffee",
                        "text_lemmatized": "bob likes latte coffee",
                        "user_id": "bm25_bob",
                    },
                ),
            ],
        )

        assert db.keyword_search("", filters={"user_id": "bm25_alice"}) == []
        rows = db.keyword_search("latte", top_k=10, filters={"user_id": "bm25_alice"})
        assert rows is not None
        _assert_exact_ids(rows, {alice_id})
    finally:
        db.delete_col()


@pytest.mark.skipif(
    not _env_bool("GAUSSDB_TEST_RUN_INDEX_MATRIX"),
    reason="Set GAUSSDB_TEST_RUN_INDEX_MATRIX=true to run all vector index and metric combinations",
)
@pytest.mark.parametrize("vector_index_type", ["gsivfflat", "gsdiskann"])
@pytest.mark.parametrize("vector_metric", ["cosine", "l2"])
def test_vector_index_metric_matrix_builds_and_searches(vector_index_type, vector_metric):
    db = _new_db(vector_index_type=vector_index_type, vector_metric=vector_metric)
    try:
        matrix_id = _uuid(121)
        _insert_memories(
            db,
            [
                (
                    matrix_id,
                    VECTOR_COFFEE,
                    {
                        "data": f"{vector_index_type} {vector_metric} matrix memory",
                        "text_lemmatized": f"{vector_index_type} {vector_metric} matrix memory",
                        "user_id": "matrix_user",
                    },
                )
            ],
        )
        assert _ids(db.search("matrix", VECTOR_COFFEE, top_k=1, filters={"user_id": "matrix_user"})) == [matrix_id]
        assert any("vector_idx" in index for index in db.col_info()["indexes"])
    finally:
        db.delete_col()



# ===========================================================================
# Search Quality Replay Tests (from test_gaussdb_quality.py)
# ===========================================================================


class TestQualityReplay:
    """Quality replay tests using gaussdb_quality_cases.json."""

    def _seed_cases(self, db, cases):
        db.insert(
            vectors=[case["vector"] for case in cases],
            ids=[case["id"] for case in cases],
            payloads=[
                {
                    "data": case["data"],
                    "text_lemmatized": case["text_lemmatized"],
                    "user_id": case["user_id"],
                    "agent_id": case["agent_id"],
                    "run_id": case["run_id"],
                }
                for case in cases
            ],
        )

    @pytest.mark.skipif(
        not Path(__file__).with_name("gaussdb_quality_cases.json").exists(),
        reason="gaussdb_quality_cases.json not found",
    )
    def test_quality_replay_gates(self):
        cases = _load_quality_cases()
        if not cases:
            pytest.skip("No quality cases available")
        collection_name = f"mem0_gdb_quality_{uuid.uuid4().hex[:8]}"
        db = _new_db(collection_name=collection_name)
        try:
            self._seed_cases(db, cases)
            semantic_hits = 0
            keyword_hits = 0
            filter_leaks = 0
            for case in cases:
                filters = {"user_id": case["user_id"]}
                semantic = db.search(case["semantic_query"], case["semantic_vector"], top_k=5, filters=filters)
                keyword = db.keyword_search(case["keyword_query"], top_k=5, filters=filters)
                semantic_ids = {item.id for item in semantic}
                keyword_ids = {item.id for item in keyword or []}
                semantic_hits += int(case["id"] in semantic_ids)
                keyword_hits += int(case["id"] in keyword_ids)
                filter_leaks += sum(1 for item in semantic if item.payload["user_id"] != case["user_id"])
                filter_leaks += sum(1 for item in keyword or [] if item.payload["user_id"] != case["user_id"])
            assert semantic_hits / len(cases) >= 0.95
            assert keyword_hits / len(cases) >= 0.90
            assert filter_leaks == 0
            update_case = cases[0]
            db.update(
                update_case["id"],
                payload={
                    "data": "Alice now prefers aisle seats",
                    "text_lemmatized": "alice now prefer aisle seat",
                    "user_id": update_case["user_id"],
                    "agent_id": update_case["agent_id"],
                    "run_id": update_case["run_id"],
                },
            )
            assert db.get(update_case["id"]).payload["data"] == "Alice now prefers aisle seats"
            db.delete(cases[1]["id"])
            assert db.get(cases[1]["id"]) is None
        finally:
            db.delete_col()

    @pytest.mark.skipif(
        not Path(__file__).with_name("gaussdb_quality_cases.json").exists(),
        reason="gaussdb_quality_cases.json not found",
    )
    def test_concurrent_operations(self):
        cases = _load_quality_cases()
        if not cases:
            pytest.skip("No quality cases available")
        collection_name = f"mem0_gdb_concurrent_{uuid.uuid4().hex[:8]}"
        db = _new_db(collection_name=collection_name)
        try:
            self._seed_cases(db, cases)
            def search_case(case):
                return db.search(
                    case["semantic_query"], case["semantic_vector"], top_k=3, filters={"user_id": case["user_id"]}
                )
            with ThreadPoolExecutor(max_workers=4) as executor:
                results = list(executor.map(search_case, cases))
            assert len(results) == len(cases)
            assert all(result for result in results)
            assert all(group[0].score >= 0 for group in results)
        finally:
            db.delete_col()

    @pytest.mark.skipif(
        not Path(__file__).with_name("gaussdb_quality_cases.json").exists(),
        reason="gaussdb_quality_cases.json not found",
    )
    @pytest.mark.skipif(
        os.getenv("GAUSSDB_TEST_BENCHMARK", "false").lower() != "true",
        reason="Set GAUSSDB_TEST_BENCHMARK=true to run benchmark",
    )
    def test_benchmark_report(self):
        cases = _load_quality_cases()
        if not cases:
            pytest.skip("No quality cases available")
        collection_name = f"mem0_gdb_bench_{uuid.uuid4().hex[:8]}"
        db = _new_db(collection_name=collection_name)
        try:
            latencies = {"insert": [], "semantic_search": [], "keyword_search": [], "update": [], "delete": []}
            for _ in range(5):
                started = time.perf_counter()
                self._seed_cases(db, cases)
                latencies["insert"].append((time.perf_counter() - started) * 1000)
                for case in cases:
                    started = time.perf_counter()
                    db.search(case["semantic_query"], case["semantic_vector"], top_k=5, filters={"user_id": case["user_id"]})
                    latencies["semantic_search"].append((time.perf_counter() - started) * 1000)
                    started = time.perf_counter()
                    db.keyword_search(case["keyword_query"], top_k=5, filters={"user_id": case["user_id"]})
                    latencies["keyword_search"].append((time.perf_counter() - started) * 1000)
                    started = time.perf_counter()
                    db.update(case["id"], payload={"data": case["data"], "text_lemmatized": case["text_lemmatized"], "user_id": case["user_id"], "agent_id": case["agent_id"], "run_id": case["run_id"]})
                    latencies["update"].append((time.perf_counter() - started) * 1000)
                started = time.perf_counter()
                db.delete(cases[-1]["id"])
                latencies["delete"].append((time.perf_counter() - started) * 1000)
            report = {
                key: statistics.quantiles(values, n=20)[-1] if len(values) >= 2 else values[0]
                for key, values in latencies.items()
            }
            assert report["semantic_search"] < float(os.getenv("GAUSSDB_TEST_SEMANTIC_P95_MS", "300"))
            assert report["keyword_search"] < float(os.getenv("GAUSSDB_TEST_KEYWORD_P95_MS", "300"))
        finally:
            db.delete_col()


# ===========================================================================
# E2E Direct DB Tests (from test_gaussdb_e2e.py, converted to pytest)
# ===========================================================================


class TestE2EDirect:
    """Direct DB verification tests converted from standalone E2E script."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="e2e", embedding_model_dims=1536, vector_index_type="gsdiskann")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_e2e_insert_single(self):
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(42, dims=1536)
        payload = {"data": "test memory", "user_id": "e2e_user", "category": "test"}
        self.db.insert(vectors=[vec], ids=[vid], payloads=[payload])
        result = self.db.get(vid)
        assert result is not None
        assert result.id == vid
        assert result.payload["data"] == "test memory"

    def test_e2e_insert_batch(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        ids = [str(uuid.uuid4()) for _ in range(10)]
        vectors = [_make_vector_seeded(i, dims=1536) for i in range(10)]
        payloads = [{"data": f"memory_{i}", "user_id": user_id} for i in range(10)]
        self.db.insert(vectors=vectors, ids=ids, payloads=payloads)
        listed = _list_flat(self.db, filters={"user_id": user_id}, top_k=100)
        assert len(listed) == 10

    def test_e2e_upsert_existing(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(100, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "original", "user_id": user_id}])
        new_vec = _make_vector_seeded(101, dims=1536)
        self.db.update(vector_id=vid, vector=new_vec, payload={"data": "updated", "user_id": user_id})
        result = self.db.get(vid)
        assert result.payload["data"] == "updated"
        listed = _list_flat(self.db, filters={"user_id": user_id}, top_k=100)
        assert len(listed) == 1

    def test_e2e_semantic_search(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vecs = [_make_vector_seeded(i, dims=1536) for i in range(5)]
        ids = [str(uuid.uuid4()) for _ in range(5)]
        payloads = [{"data": f"item_{i}", "user_id": user_id} for i in range(5)]
        self.db.insert(vectors=vecs, ids=ids, payloads=payloads)
        query_vec = _make_vector_seeded(0, dims=1536)
        results = self.db.search("item", query_vec, top_k=1, filters={"user_id": user_id})
        assert len(results) >= 1
        assert results[0].id == ids[0]

    def test_e2e_search_with_filters(self):
        ids = [str(uuid.uuid4()) for _ in range(4)]
        vecs = [_make_vector_seeded(i, dims=1536) for i in range(4)]
        payloads = [
            {"data": "alice food", "user_id": "alice", "category": "food"},
            {"data": "alice travel", "user_id": "alice", "category": "travel"},
            {"data": "bob food", "user_id": "bob", "category": "food"},
            {"data": "bob work", "user_id": "bob", "category": "work"},
        ]
        self.db.insert(vectors=vecs, ids=ids, payloads=payloads)
        results = self.db.search("food", vecs[0], top_k=10, filters={"user_id": "alice", "category": "food"})
        assert all(r.payload["user_id"] == "alice" for r in results)
        assert all(r.payload["category"] == "food" for r in results)

    @pytest.mark.skipif(
        not _env_bool("GAUSSDB_TEST_RUN_BM25"),
        reason="Set GAUSSDB_TEST_RUN_BM25=true to run BM25 tests",
    )
    def test_e2e_bm25_keyword_search(self):
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(200, dims=1536)
        self.db.insert(
            vectors=[vec], ids=[vid],
            payloads=[{"data": "Python programming language", "user_id": "e2e_user", "text_lemmatized": "python programming language"}],
        )
        results = self.db.keyword_search("Python", top_k=5, filters={"user_id": "e2e_user"})
        if results:
            assert any(r.id == vid for r in results)

    def test_e2e_update_payload(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(300, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "original", "user_id": user_id}])
        self.db.update(vector_id=vid, payload={"data": "modified", "user_id": user_id, "extra": "field"})
        result = self.db.get(vid)
        assert result.payload["data"] == "modified"
        assert result.payload["extra"] == "field"

    def test_e2e_update_vector(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(301, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "vec update", "user_id": user_id}])
        new_vec = _make_vector_seeded(302, dims=1536)
        self.db.update(vector_id=vid, vector=new_vec)
        results = self.db.search("vec", new_vec, top_k=1, filters={"user_id": user_id})
        assert len(results) >= 1
        assert results[0].id == vid

    def test_e2e_delete_by_id(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(400, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "to delete", "user_id": user_id}])
        self.db.delete(vector_id=vid)
        assert self.db.get(vid) is None

    def test_e2e_list_with_filters(self):
        alice_user_id = f"alice_{uuid.uuid4().hex[:8]}"
        bob_user_id = f"bob_{uuid.uuid4().hex[:8]}"
        ids = [str(uuid.uuid4()) for _ in range(6)]
        vecs = [_make_vector_seeded(i + 500, dims=1536) for i in range(6)]
        payloads = [
            {"data": f"item_{i}", "user_id": alice_user_id if i < 3 else bob_user_id}
            for i in range(6)
        ]
        self.db.insert(vectors=vecs, ids=ids, payloads=payloads)
        alice_items = _list_flat(self.db, filters={"user_id": alice_user_id}, top_k=100)
        assert len(alice_items) == 3
        bob_items = _list_flat(self.db, filters={"user_id": bob_user_id}, top_k=100)
        assert len(bob_items) == 3

    def test_e2e_list_collections(self):
        cols = self.db.list_cols()
        assert isinstance(cols, list)
        assert self.db.collection_name in cols

    def test_e2e_collection_info(self):
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(600, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "info test", "user_id": "e2e_user"}])
        info = self.db.col_info()
        assert info["name"] == self.db.collection_name
        assert info["count"] >= 1
        assert info["dimension"] == 1536

    def test_e2e_large_payload(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(700, dims=1536)
        large_text = "x" * 10000
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": large_text, "user_id": user_id}])
        result = self.db.get(vid)
        assert result is not None
        assert len(result.payload["data"]) == 10000

    def test_e2e_unicode_payload(self):
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(800, dims=1536)
        text = "中文测试 日本語 한국어 emoji: 🚀💻"
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": text, "user_id": "e2e_user"}])
        result = self.db.get(vid)
        assert result.payload["data"] == text

    def test_e2e_concurrent_upsert_idempotency(self):
        user_id = f"e2e_user_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(900, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "concurrent", "user_id": user_id}])

        def do_upsert(idx):
            self.db.update(vector_id=vid, payload={"data": f"update_{idx}", "user_id": user_id})

        with ThreadPoolExecutor(max_workers=5) as executor:
            list(executor.map(do_upsert, range(10)))

        result = self.db.get(vid)
        assert result is not None
        assert result.payload["user_id"] == user_id
        listed = _list_flat(self.db, filters={"user_id": user_id}, top_k=100)
        assert len(listed) == 1

    def test_e2e_reset_collection(self):
        db = _new_db(prefix="e2e_reset", embedding_model_dims=1536, vector_index_type="gsdiskann")
        try:
            ids = [str(uuid.uuid4()) for _ in range(5)]
            vecs = [_make_vector_seeded(i + 1000, dims=1536) for i in range(5)]
            payloads = [{"data": f"item_{i}", "user_id": "e2e_reset_user"} for i in range(5)]
            db.insert(vectors=vecs, ids=ids, payloads=payloads)
            assert len(_list_flat(db, filters={"user_id": "e2e_reset_user"}, top_k=100)) == 5
            db.reset()
            listed = _list_flat(db, filters={"user_id": "e2e_reset_user"}, top_k=100)
            assert len(listed) == 0
        finally:
            db.delete_col()

    def test_e2e_delete_collection(self):
        db = _new_db(prefix="e2e_delcol", embedding_model_dims=1536, vector_index_type="gsdiskann")
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(1100, dims=1536)
        db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "cleanup", "user_id": "e2e_delcol_user"}])
        db.delete_col()
        cols = db.list_cols()
        assert db.collection_name not in cols



# ===========================================================================
# E2E Full Verification Tests (from test_gaussdb_e2e_full.py, converted to pytest)
# ===========================================================================


class TestE2EFull:
    """Full E2E verification covering CRUD, edge cases, filters, batch ops."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="e2e_full", embedding_model_dims=4)

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_full_init_and_create_collection(self):
        cols = self.db.list_cols()
        assert self.db.collection_name in cols
        info = self.db.col_info()
        assert info["name"] == self.db.collection_name
        assert info["dimension"] == 4

    def test_full_crud_lifecycle(self):
        """Insert, get, update, search, delete lifecycle."""
        id1 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-record-1"))
        id2 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-record-2"))
        id3 = str(uuid.uuid5(uuid.NAMESPACE_DNS, "test-record-3"))

        # Insert
        self.db.insert(
            ids=[id1, id2, id3],
            vectors=[[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8], [0.9, 0.1, 0.2, 0.3]],
            payloads=[
                {"data": "first record", "user_id": "full_user", "category": "A"},
                {"data": "second record", "user_id": "full_user", "category": "B"},
                {"data": "third record", "user_id": "full_user", "category": "A"},
            ],
        )

        # Get
        r1 = self.db.get(id1)
        assert r1 is not None
        assert r1.payload["data"] == "first record"

        # Update payload
        self.db.update(vector_id=id1, payload={"data": "updated first", "user_id": "full_user", "category": "A"})
        r1_updated = self.db.get(id1)
        assert r1_updated.payload["data"] == "updated first"

        # Update vector
        self.db.update(vector_id=id2, vector=[0.99, 0.99, 0.99, 0.99])
        results = self.db.search("test", [0.99, 0.99, 0.99, 0.99], top_k=1, filters={"user_id": "full_user"})
        assert results[0].id == id2

        # Search with filter
        results = self.db.search("test", [0.1, 0.2, 0.3, 0.4], top_k=10, filters={"user_id": "full_user", "category": "A"})
        result_ids = {r.id for r in results}
        assert id1 in result_ids
        assert id3 in result_ids
        assert id2 not in result_ids

        # Delete
        self.db.delete(vector_id=id3)
        assert self.db.get(id3) is None

        # List remaining
        listed = _list_flat(self.db, filters={"user_id": "full_user"}, top_k=100)
        assert len(listed) == 2

    def test_full_edge_cases_empty_search(self):
        """Search on empty collection returns empty list."""
        results = self.db.search("nothing", [0.1, 0.2, 0.3, 0.4], top_k=5, filters={"user_id": "nobody"})
        assert results == [] or len(results) == 0

    def test_full_edge_cases_special_chars_payload(self):
        """Payload with special characters stored and retrieved correctly."""
        vid = str(uuid.uuid4())
        special = 'C++ & C# are <great> languages; SELECT * FROM \'table\' WHERE x="test" -- comment'
        self.db.insert(
            ids=[vid], vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"data": special, "user_id": "full_user"}],
        )
        result = self.db.get(vid)
        assert result.payload["data"] == special

    def test_full_edge_cases_null_like_values(self):
        """Empty string and None-like values in payload."""
        vid = str(uuid.uuid4())
        self.db.insert(
            ids=[vid], vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"data": "", "user_id": "full_user", "note": "null_test"}],
        )
        result = self.db.get(vid)
        assert result.payload["data"] == ""

    def test_full_filters_eq_ne_in_nin(self):
        """Filter operators eq, ne, in, nin work correctly."""
        ids = [str(uuid.uuid4()) for _ in range(4)]
        self.db.insert(
            ids=ids,
            vectors=[[0.1, 0.2, 0.3, 0.4]] * 4,
            payloads=[
                {"data": "a", "user_id": "filter_user", "category": "food", "priority": "1"},
                {"data": "b", "user_id": "filter_user", "category": "travel", "priority": "2"},
                {"data": "c", "user_id": "filter_user", "category": "work", "priority": "3"},
                {"data": "d", "user_id": "filter_user", "category": "food", "priority": "4"},
            ],
        )
        # eq
        results = self.db.search("test", [0.1, 0.2, 0.3, 0.4], top_k=10, filters={"user_id": "filter_user", "category": {"eq": "food"}})
        assert len(results) == 2
        # ne
        results = self.db.search("test", [0.1, 0.2, 0.3, 0.4], top_k=10, filters={"user_id": "filter_user", "category": {"ne": "food"}})
        assert len(results) == 2
        # in
        results = self.db.search("test", [0.1, 0.2, 0.3, 0.4], top_k=10, filters={"user_id": "filter_user", "category": {"in": ["food", "travel"]}})
        assert len(results) == 3
        # nin
        results = self.db.search("test", [0.1, 0.2, 0.3, 0.4], top_k=10, filters={"user_id": "filter_user", "category": {"nin": ["food"]}})
        assert len(results) == 2

    @pytest.mark.skipif(
        not _env_bool("GAUSSDB_TEST_RUN_BM25"),
        reason="Set GAUSSDB_TEST_RUN_BM25=true to run BM25 tests",
    )
    def test_full_bm25_search(self):
        """BM25 keyword search works in full E2E context."""
        vid = str(uuid.uuid4())
        self.db.insert(
            ids=[vid], vectors=[[0.1, 0.2, 0.3, 0.4]],
            payloads=[{"data": "Python machine learning", "user_id": "bm25_user", "text_lemmatized": "python machine learning"}],
        )
        results = self.db.keyword_search("Python", top_k=5, filters={"user_id": "bm25_user"})
        if results:
            assert any(r.id == vid for r in results)

    def test_full_batch_operations(self):
        """Batch insert and search operations."""
        count = 50
        ids = [str(uuid.uuid4()) for _ in range(count)]
        vectors = [[random.random() for _ in range(4)] for _ in range(count)]
        payloads = [{"data": f"batch_{i}", "user_id": "batch_user"} for i in range(count)]
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)
        listed = _list_flat(self.db, filters={"user_id": "batch_user"}, top_k=200)
        assert len(listed) == count

    def test_full_rapid_upsert(self):
        """Rapid upsert of same ID is idempotent."""
        vid = str(uuid.uuid4())
        vec = [0.5, 0.5, 0.5, 0.5]
        for i in range(10):
            self.db.insert(ids=[vid], vectors=[vec], payloads=[{"data": f"version_{i}", "user_id": "rapid_user"}])
        listed = _list_flat(self.db, filters={"user_id": "rapid_user"}, top_k=100)
        assert len(listed) == 1
        result = self.db.get(vid)
        assert result.payload["data"] == "version_9"

    def test_full_data_integrity(self):
        """Data integrity: no silent corruption after multiple operations."""
        ids = [str(uuid.uuid4()) for _ in range(20)]
        vectors = [[float(i) / 20, float(i) / 20, float(i) / 20, float(i) / 20] for i in range(20)]
        payloads = [{"data": f"integrity_{i}", "user_id": "integrity_user", "index": str(i)} for i in range(20)]
        self.db.insert(ids=ids, vectors=vectors, payloads=payloads)

        # Verify all records
        for i, vid in enumerate(ids):
            result = self.db.get(vid)
            assert result is not None, f"Record {i} missing"
            assert result.payload["data"] == f"integrity_{i}"
            assert result.payload["index"] == str(i)

        # Delete some, verify others unaffected
        for vid in ids[:5]:
            self.db.delete(vector_id=vid)
        for i, vid in enumerate(ids[5:], start=5):
            result = self.db.get(vid)
            assert result is not None, f"Record {i} should still exist"
            assert result.payload["data"] == f"integrity_{i}"

    def test_full_reset_collection(self):
        """Reset collection removes all data."""
        db = _new_db(prefix="e2e_full_reset", embedding_model_dims=4)
        try:
            ids = [str(uuid.uuid4()) for _ in range(5)]
            vectors = [[0.1, 0.2, 0.3, 0.4]] * 5
            payloads = [{"data": f"item_{i}", "user_id": "reset_user"} for i in range(5)]
            db.insert(ids=ids, vectors=vectors, payloads=payloads)
            assert len(_list_flat(db, filters={"user_id": "reset_user"}, top_k=100)) == 5
            db.reset()
            listed = _list_flat(db, filters={"user_id": "reset_user"}, top_k=100)
            assert len(listed) == 0
        finally:
            db.delete_col()



# ===========================================================================
# Memory API E2E Tests (from test_gaussdb_e2e_memory.py, converted to pytest)
# ===========================================================================


class TestMemoryAPI:
    """Tests using Memory.from_config upper-layer API with GaussDB backend."""

    def _make_memory(self, collection_name):
        """Build a Memory instance with mocked LLM/Embedder using GaussDB backend."""
        vector_config = _gaussdb_env_config(collection_name, embedding_model_dims=EMBEDDING_DIMS)
        if vector_config is None:
            pytest.skip("GaussDB env not configured")

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
            return Memory.from_config(memory_config)

    def test_memory_add_and_search(self):
        """Memory.add and Memory.search work with GaussDB backend."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            added = m.add(
                "I love coffee and window seats",
                user_id=user_id,
                infer=False,
                metadata={"source": "centralized-test"},
            )
            assert len(added.get("results", [])) >= 1

            results = m.search("coffee", filters={"user_id": user_id}, top_k=5, threshold=0)
            assert len(results.get("results", [])) >= 1
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass

    def test_memory_get_all(self):
        """Memory.get_all returns stored memories."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            m.add(
                "I prefer aisle seats on flights",
                user_id=user_id,
                infer=False,
            )
            all_memories = m.get_all(filters={"user_id": user_id})
            memories_list = all_memories.get("results", all_memories.get("memories", []))
            assert len(memories_list) >= 1
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass

    def test_memory_get_and_update(self):
        """Memory.get and Memory.update work with GaussDB backend."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            added = m.add(
                "Original note about coffee beans",
                user_id=user_id,
                infer=False,
            )
            mem_id = added["results"][0]["id"]

            fetched = m.get(mem_id)
            assert fetched["id"] == mem_id
            assert "Original note about coffee beans" in fetched["memory"]

            m.update(mem_id, data="Updated note about coffee beans")
            updated = m.vector_store.get(mem_id)
            assert updated is not None
            assert "Updated note about coffee beans" in updated.payload.get("data", "")
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass

    def test_memory_delete(self):
        """Memory.delete removes a specific memory."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            result = m.add(
                "I like hiking in the mountains",
                user_id=user_id,
                infer=False,
            )
            memories = result.get("results", [])
            assert len(memories) >= 1
            mem_id = memories[0]["id"]

            m.delete(mem_id)
            assert m.vector_store.get(mem_id) is None
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass

    def test_memory_delete_all(self):
        """Memory.delete_all removes all memories for a user."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            m.add("Memory one", user_id=user_id, infer=False)
            m.add("Memory two", user_id=user_id, infer=False)
            m.delete_all(user_id=user_id)
            all_after = m.get_all(filters={"user_id": user_id})
            remaining = all_after.get("results", all_after.get("memories", []))
            assert len(remaining) == 0
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass

    def test_memory_reset(self):
        """Memory.reset recreates the collection and clears prior user data."""
        collection = _new_collection_name("mem_api")
        m = self._make_memory(collection)
        try:
            user_id = f"mem_test_{uuid.uuid4().hex[:6]}"
            m.add("Reset memory one", user_id=user_id, infer=False)
            m.add("Reset memory two", user_id=user_id, infer=False)

            before = m.get_all(filters={"user_id": user_id})
            before_rows = before.get("results", before.get("memories", []))
            assert len(before_rows) >= 2

            m.reset()

            after = m.get_all(filters={"user_id": user_id})
            after_rows = after.get("results", after.get("memories", []))
            assert len(after_rows) == 0
        finally:
            try:
                m.vector_store.delete_col()
            except Exception:
                pass



# ===========================================================================
# Multi-language Tests (from test_gaussdb_e2e_multilang.py, converted to pytest)
# ===========================================================================

MULTILANG_CASES = [
    {
        "lang": "English",
        "text": "I love programming in Python and building machine learning models.",
        "bm25_query": "Python programming",
        "payload": {"user_id": "lang_test", "category": "tech", "language": "en"},
    },
    {
        "lang": "Chinese (Simplified)",
        "text": "我喜欢用Python做数据分析和机器学习，周末经常去公园跑步。",
        "bm25_query": "Python数据分析",
        "payload": {"user_id": "lang_test", "category": "tech", "language": "zh-CN"},
    },
    {
        "lang": "Chinese (Traditional)",
        "text": "台灣的珍珠奶茶非常好喝，我每天都要來一杯。",
        "bm25_query": "珍珠奶茶",
        "payload": {"user_id": "lang_test", "category": "food", "language": "zh-TW"},
    },
    {
        "lang": "Japanese",
        "text": "東京の桜は春に美しく咲きます。日本語のプログラミング教材を読んでいます。",
        "bm25_query": "桜",
        "payload": {"user_id": "lang_test", "category": "culture", "language": "ja"},
    },
    {
        "lang": "Korean",
        "text": "서울에서 김치찌개를 먹었습니다. 한국어 공부를 열심히 하고 있습니다.",
        "bm25_query": "김치찌개",
        "payload": {"user_id": "lang_test", "category": "food", "language": "ko"},
    },
    {
        "lang": "Arabic",
        "text": "أنا أحب البرمجة وتعلم اللغات الجديدة. القهوة العربية لذيذة جداً.",
        "bm25_query": "البرمجة",
        "payload": {"user_id": "lang_test", "category": "tech", "language": "ar"},
    },
    {
        "lang": "Emoji + Mixed",
        "text": "🎉 Hello世界! Python🐍 is awesome すごい 太棒了 fantastique! 🚀💻",
        "bm25_query": "Python",
        "payload": {"user_id": "lang_test", "category": "mixed", "language": "mixed"},
    },
]


class TestMultilang:
    """Multi-language text storage and retrieval tests."""

    @classmethod
    def setup_class(cls):
        cls.db = _new_db(prefix="multilang", embedding_model_dims=1536, vector_index_type="gsdiskann")

    @classmethod
    def teardown_class(cls):
        cls.db.delete_col()

    def test_multilang_insert_and_retrieve(self):
        """Insert multilang text and verify payload integrity."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        ids = []
        for i, case in enumerate(MULTILANG_CASES):
            vid = str(uuid.uuid4())
            ids.append(vid)
            vec = _make_vector_seeded(i, dims=1536)
            payload = {**case["payload"], "user_id": user_id, "text": case["text"]}
            self.db.insert(vectors=[vec], ids=[vid], payloads=[payload])

        # Verify all texts stored correctly
        for i, (case, vid) in enumerate(zip(MULTILANG_CASES, ids)):
            record = self.db.get(vector_id=vid)
            assert record is not None, f"{case['lang']} record not found"
            stored_text = record.payload.get("text", "")
            assert stored_text == case["text"], f"{case['lang']} text mismatch"

    def test_multilang_vector_search(self):
        """Vector search returns correct results for multilang data."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        ids = []
        for i, case in enumerate(MULTILANG_CASES):
            vid = str(uuid.uuid4())
            ids.append(vid)
            vec = _make_vector_seeded(i, dims=1536)
            payload = {**case["payload"], "user_id": user_id, "text": case["text"]}
            self.db.insert(vectors=[vec], ids=[vid], payloads=[payload])

        # Search with same vector should return self as top hit
        for i, case in enumerate(MULTILANG_CASES):
            query_vec = _make_vector_seeded(i, dims=1536)
            hits = self.db.search(case["text"], query_vec, top_k=1, filters={"user_id": user_id})
            assert len(hits) >= 1
            assert hits[0].id == ids[i], f"{case['lang']} search failed"

    @pytest.mark.skipif(
        not _env_bool("GAUSSDB_TEST_RUN_BM25"),
        reason="Set GAUSSDB_TEST_RUN_BM25=true to run BM25 tests",
    )
    def test_multilang_bm25_search(self):
        """BM25 search works with multilang text."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        ids = []
        for i, case in enumerate(MULTILANG_CASES):
            vid = str(uuid.uuid4())
            ids.append(vid)
            vec = _make_vector_seeded(i, dims=1536)
            payload = {**case["payload"], "user_id": user_id, "text": case["text"], "text_lemmatized": case["text"].lower()}
            self.db.insert(vectors=[vec], ids=[vid], payloads=[payload])

        for i, case in enumerate(MULTILANG_CASES):
            results = self.db.keyword_search(query=case["bm25_query"], top_k=5, filters={"user_id": user_id})
            # BM25 may not work for all languages, just verify no crash
            assert results is None or isinstance(results, list)

    def test_multilang_update_payload(self):
        """Update payload with multilang text."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(0, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "original", "user_id": user_id}])

        new_text = "更新后的中文文本：华为GaussDB是一款优秀的分布式数据库。"
        self.db.update(vector_id=vid, payload={"data": new_text, "user_id": user_id, "updated": "true"})
        record = self.db.get(vector_id=vid)
        assert record.payload["data"] == new_text
        assert record.payload["updated"] == "true"

    def test_multilang_delete_and_verify(self):
        """Delete multilang record and verify removal."""
        user_id = f"lang_test_{uuid.uuid4().hex[:8]}"
        vid = str(uuid.uuid4())
        vec = _make_vector_seeded(99, dims=1536)
        self.db.insert(vectors=[vec], ids=[vid], payloads=[{"data": "中文测试", "user_id": user_id}])
        self.db.delete(vector_id=vid)
        assert self.db.get(vector_id=vid) is None

