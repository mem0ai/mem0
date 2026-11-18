"""
Tests for the ClickHouse vector store.

These tests require a real ClickHouse instance to be reachable (e.g. via
Docker: `docker run -d -p 8123:8123 -e CLICKHOUSE_PASSWORD=<pw> clickhouse/clickhouse-server`).
Tests are skipped automatically if ClickHouse isn't reachable, matching the
convention used by other external-provider tests in this repo (see
tests/vector_stores/test_pgvector.py).
"""

import socket
import pytest
from mem0.vector_stores.clickhouse import ClickhouseDB

CLICKHOUSE_HOST = "localhost"
CLICKHOUSE_PORT = 8123
CLICKHOUSE_PASSWORD = "mem0pass"

def _clickhouse_reachable():
    try:
        with socket.create_connection((CLICKHOUSE_HOST, CLICKHOUSE_PORT), timeout=1):
            return True
    except OSError:
        return False

pytestmark = pytest.mark.skipif(
    not _clickhouse_reachable(),
    reason="ClickHouse is not reachable on localhost:8123; skipping ClickHouse vector store tests.",
)

@pytest.fixture
def db():
    """A fresh ClickHouse collection for each test, cleaned up afterward."""
    store = ClickhouseDB(
        collection_name="test_mem0_clickhouse",
        embedding_model_dims=4,
        host=CLICKHOUSE_HOST,
        port=CLICKHOUSE_PORT,
        password=CLICKHOUSE_PASSWORD,
    )
    yield store
    store.delete_col()

class TestClickhouseDB:
    def test_create_col_is_idempotent(self, db):
        # Calling create_col again should not raise or duplicate the table.
        db.create_col("test_mem0_clickhouse", 4, distance="cosine")
        assert "test_mem0_clickhouse" in db.list_cols()

    def test_insert_and_get(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "hello"}], ids=["1"])
        result = db.get("1")
        assert result is not None
        assert result.id == "1"
        assert result.payload == {"text": "hello"}

    def test_get_missing_id_returns_none(self, db):
        assert db.get("does-not-exist") is None

    def test_insert_same_id_replaces_not_duplicates(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "first"}], ids=["1"])
        db.insert(vectors=[[0.5, 0.5, 0.5, 0.5]], payloads=[{"text": "replaced"}], ids=["1"])
        rows = db.list(top_k=100)
        matching = [r for r in rows if r.id == "1"]
        assert len(matching) == 1
        assert matching[0].payload == {"text": "replaced"}

    def test_search_ranks_by_similarity(self, db):
        db.insert(
            vectors=[[0.1, 0.2, 0.3, 0.4], [0.9, 0.8, 0.1, 0.2]],
            payloads=[{"text": "close"}, {"text": "far"}],
            ids=["1", "2"],
        )
        results = db.search(query="q", vectors=[0.1, 0.2, 0.3, 0.4], top_k=2)
        assert results[0].id == "1"
        assert results[0].score >= results[1].score

    def test_delete_removes_row(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "temp"}], ids=["1"])
        db.delete("1")
        # ClickHouse deletes are async; give the mutation a brief moment.
        import time

        time.sleep(1)
        assert db.get("1") is None

    def test_update_payload_keeps_existing_vector(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "old"}], ids=["1"])
        db.update("1", payload={"text": "new"})
        result = db.get("1")
        assert result.payload == {"text": "new"}
        assert result.vector == pytest.approx([0.1, 0.2, 0.3, 0.4], abs=1e-4)

    def test_col_info_reports_row_count(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "a"}], ids=["1"])
        info = db.col_info()
        assert info["row_count"] == 1

    def test_reset_empties_collection(self, db):
        db.insert(vectors=[[0.1, 0.2, 0.3, 0.4]], payloads=[{"text": "a"}], ids=["1"])
        db.reset()
        assert db.list(top_k=100) == []
