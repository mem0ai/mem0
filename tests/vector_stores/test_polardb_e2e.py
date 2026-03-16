"""
End-to-end integration test for the PolarDB vector store layer.

Tests the PolarDB class directly (without the Memory abstraction), exercising
all 11 VectorStoreBase methods against a real PolarDB MySQL instance.

Required environment variables:
    POLARDB_HOST       PolarDB MySQL hostname (must include IMCI node)
    POLARDB_USER       Database user
    POLARDB_PASSWORD   Database password
    POLARDB_DATABASE   Database name

Optional:
    POLARDB_PORT       Database port (default: 3306)

Run:
    POLARDB_HOST=xxx POLARDB_USER=xxx POLARDB_PASSWORD=xxx \
    POLARDB_DATABASE=xxx \
        python -m pytest tests/vector_stores/test_polardb_e2e.py -v -s
"""

import os
import time
import uuid

import numpy as np
import pytest

# ── skip conditions ──────────────────────────────────────────────────────────
_REQUIRED_ENV = ["POLARDB_HOST", "POLARDB_USER", "POLARDB_PASSWORD", "POLARDB_DATABASE"]
_MISSING = [v for v in _REQUIRED_ENV if not os.environ.get(v)]

pytestmark = pytest.mark.skipif(
    len(_MISSING) > 0,
    reason=f"PolarDB E2E test requires env vars: {', '.join(_MISSING)}",
)

# ── helpers ──────────────────────────────────────────────────────────────────
_DIMS = 4
_COLLECTION = f"polardb_e2e_{uuid.uuid4().hex[:8]}"
_IMCI_SYNC_WAIT = 2


def _rand_vec(dims=_DIMS):
    """Generate a random unit vector."""
    v = np.random.randn(dims).astype("float32")
    return (v / np.linalg.norm(v)).tolist()


# ── fixtures ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def store():
    """Create a PolarDB vector store instance, tear down after all tests."""
    from mem0.vector_stores.polardb import PolarDB

    db = PolarDB(
        host=os.environ["POLARDB_HOST"],
        port=int(os.environ.get("POLARDB_PORT", "3306")),
        user=os.environ["POLARDB_USER"],
        password=os.environ["POLARDB_PASSWORD"],
        database=os.environ["POLARDB_DATABASE"],
        collection_name=_COLLECTION,
        embedding_model_dims=_DIMS,
        index_type="FAISS_HNSW_FLAT",
    )
    yield db
    try:
        db.delete_col()
    except Exception:
        pass


# ── tests (ordered by name so they run sequentially) ─────────────────────────

class TestPolarDBVectorE2E:
    """Full lifecycle tests for the PolarDB vector store."""

    # ── 1. collection created ────────────────────────────────────────────────

    def test_01_collection_created(self, store):
        """The collection table should exist after __init__."""
        cols = store.list_cols()
        assert _COLLECTION in cols

    def test_02_col_info(self, store):
        """col_info() should return metadata about the collection."""
        info = store.col_info()
        assert info["name"] == _COLLECTION

    # ── 2. insert single ────────────────────────────────────────────────────

    def test_03_insert_single(self, store):
        """insert() a single vector."""
        store.insert(
            vectors=[_rand_vec()],
            ids=["vec-001"],
            payloads=[{"user_id": "alice", "data": "hello world"}],
        )
        time.sleep(_IMCI_SYNC_WAIT)

    def test_04_get(self, store):
        """get() retrieves the inserted vector."""
        result = store.get("vec-001")
        assert result is not None
        assert result.id == "vec-001"
        assert result.payload["data"] == "hello world"

    def test_05_get_not_found(self, store):
        """get() returns None for non-existent ID."""
        result = store.get("non-existent-id")
        assert result is None

    # ── 3. batch insert ──────────────────────────────────────────────────────

    def test_06_insert_batch(self, store):
        """insert() multiple vectors at once."""
        store.insert(
            vectors=[_rand_vec(), _rand_vec(), _rand_vec()],
            ids=["vec-002", "vec-003", "vec-004"],
            payloads=[
                {"user_id": "alice", "data": "item two"},
                {"user_id": "bob", "data": "item three"},
                {"user_id": "alice", "data": "item four"},
            ],
        )
        time.sleep(_IMCI_SYNC_WAIT)

    # ── 4. search ────────────────────────────────────────────────────────────

    def test_07_search_basic(self, store):
        """search() returns results ordered by distance."""
        results = store.search(query="test", vectors=_rand_vec(), limit=10)
        assert len(results) == 4
        # scores should be in ascending order (closer = lower)
        scores = [r.score for r in results]
        assert scores == sorted(scores)

    def test_08_search_returns_nearest(self, store):
        """search() with a known vector returns it as the nearest."""
        known_vec = _rand_vec()
        store.insert(
            vectors=[known_vec],
            ids=["vec-exact"],
            payloads=[{"user_id": "alice", "data": "exact match"}],
        )
        time.sleep(_IMCI_SYNC_WAIT)

        results = store.search(query="exact", vectors=known_vec, limit=1)
        assert len(results) == 1
        assert results[0].id == "vec-exact"
        assert results[0].score < 0.01  # should be very close to 0

    def test_09_search_with_filter(self, store):
        """search() with filters narrows results."""
        results = store.search(
            query="test",
            vectors=_rand_vec(),
            limit=10,
            filters={"user_id": "bob"},
        )
        assert len(results) == 1
        assert results[0].payload["user_id"] == "bob"

    # ── 5. list ──────────────────────────────────────────────────────────────

    def test_10_list_all(self, store):
        """list() returns all vectors."""
        results = store.list(limit=100)
        assert len(results) == 1  # double-wrapped
        assert len(results[0]) == 5  # vec-001..004 + vec-exact

    def test_11_list_with_filter(self, store):
        """list() with filters narrows results."""
        results = store.list(filters={"user_id": "alice"}, limit=100)
        assert len(results[0]) == 4  # vec-001, vec-002, vec-004, vec-exact

    # ── 6. update ────────────────────────────────────────────────────────────

    def test_12_update_vector(self, store):
        """update() can change the vector."""
        new_vec = _rand_vec()
        store.update(vector_id="vec-001", vector=new_vec)
        time.sleep(_IMCI_SYNC_WAIT)

        # search for the new vector — vec-001 should be nearest
        results = store.search(query="test", vectors=new_vec, limit=1)
        assert results[0].id == "vec-001"

    def test_13_update_payload(self, store):
        """update() can change the payload."""
        store.update(
            vector_id="vec-001",
            payload={"user_id": "alice", "data": "updated payload"},
        )
        result = store.get("vec-001")
        assert result.payload["data"] == "updated payload"

    # ── 7. delete ────────────────────────────────────────────────────────────

    def test_14_delete(self, store):
        """delete() removes a vector."""
        store.delete("vec-exact")
        time.sleep(_IMCI_SYNC_WAIT)

        result = store.get("vec-exact")
        assert result is None

        results = store.list(limit=100)
        assert len(results[0]) == 4  # vec-001..004

    # ── 8. upsert (insert with ON DUPLICATE KEY) ────────────────────────────

    def test_15_upsert_via_insert(self, store):
        """insert() with existing ID updates instead of failing."""
        new_vec = _rand_vec()
        store.insert(
            vectors=[new_vec],
            ids=["vec-001"],
            payloads=[{"user_id": "alice", "data": "upserted"}],
        )
        result = store.get("vec-001")
        assert result.payload["data"] == "upserted"

    # ── 9. reset ─────────────────────────────────────────────────────────────

    def test_16_reset(self, store):
        """reset() clears all data and recreates the table."""
        store.reset()
        time.sleep(_IMCI_SYNC_WAIT)

        results = store.list(limit=100)
        assert len(results[0]) == 0

    def test_17_insert_after_reset(self, store):
        """Table is usable after reset()."""
        store.insert(
            vectors=[_rand_vec()],
            ids=["vec-after-reset"],
            payloads=[{"user_id": "carol", "data": "post reset"}],
        )
        result = store.get("vec-after-reset")
        assert result is not None
        assert result.payload["data"] == "post reset"

    # ── 10. delete_col ───────────────────────────────────────────────────────

    def test_18_delete_col(self, store):
        """delete_col() drops the table."""
        store.delete_col()
        cols = store.list_cols()
        assert _COLLECTION not in cols
