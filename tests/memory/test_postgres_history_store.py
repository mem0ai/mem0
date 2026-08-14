"""PostgresHistoryStore tests.

Contract coverage runs against SQLAlchemy sqlite:// in test_history_store.py.
This module exercises Postgres-specific wiring and, when
MEM0_HISTORY_DATABASE_URL is set, a real PostgreSQL instance.
"""

import os
import threading
import uuid

import pytest

from mem0.memory.history_store.postgres import PostgresHistoryStore

REAL_PG_URL = os.environ.get("MEM0_HISTORY_DATABASE_URL")


@pytest.fixture
def store():
    mgr = PostgresHistoryStore("sqlite:///:memory:")
    yield mgr
    mgr.close()


class TestPostgresHistoryStoreSqliteDialect:
    def test_concurrent_writes(self, store):
        memory_id = str(uuid.uuid4())
        errors = []

        def _write(i):
            try:
                store.add_history(memory_id, None, f"n{i}", "ADD", created_at=f"2026-01-01T00:00:{i:02d}")
            except Exception as exc:  # pragma: no cover - surfaced via errors
                errors.append(exc)

        threads = [threading.Thread(target=_write, args=(i,)) for i in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(store.get_history(memory_id)) == 8

    def test_close_then_reset_raises(self, store):
        store.close()
        with pytest.raises(RuntimeError, match="closed"):
            store.reset()

    def test_empty_batch_is_noop(self, store):
        store.batch_add_history([])
        assert store.get_history("anything") == []


@pytest.mark.skipif(not REAL_PG_URL, reason="MEM0_HISTORY_DATABASE_URL not set")
class TestPostgresHistoryStoreIntegration:
    @pytest.fixture
    def pg_store(self):
        mgr = PostgresHistoryStore(REAL_PG_URL)
        yield mgr
        try:
            mgr.reset()
        finally:
            mgr.close()

    def test_add_get_and_messages(self, pg_store):
        memory_id = str(uuid.uuid4())
        pg_store.add_history(memory_id, None, "pg-memory", "ADD", actor_id="a1", role="user")
        rows = pg_store.get_history(memory_id)
        assert rows[0]["new_memory"] == "pg-memory"
        scope = f"user:{uuid.uuid4()}"
        pg_store.save_messages([{"role": "user", "content": "hello", "name": None}], scope)
        assert pg_store.get_last_messages(scope)[0]["content"] == "hello"
