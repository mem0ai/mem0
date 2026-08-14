"""Contract tests for pluggable history stores plus factory wiring."""

import os
import tempfile
import uuid
from datetime import datetime

import pytest

from mem0.configs.base import HistoryStoreConfig, MemoryConfig
from mem0.memory.history_store.base import HistoryStoreBase
from mem0.memory.history_store.postgres import PostgresHistoryStore
from mem0.memory.storage import SQLiteManager
from mem0.utils.factory import HistoryStoreFactory

_PGVECTOR_STUB = {
    "provider": "pgvector",
    "config": {
        "host": "localhost",
        "port": 5432,
        "user": "user",
        "password": "pass",
        "dbname": "mem0",
    },
}


def _memory_config(**kwargs):
    kwargs.setdefault("vector_store", _PGVECTOR_STUB)
    return MemoryConfig(**kwargs)


@pytest.fixture
def sqlite_store():
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    store = SQLiteManager(temp_db.name)
    yield store
    if store.connection:
        store.close()
    if os.path.exists(temp_db.name):
        os.unlink(temp_db.name)


@pytest.fixture
def sqlalchemy_store():
    store = PostgresHistoryStore("sqlite:///:memory:")
    yield store
    store.close()


@pytest.fixture(params=["sqlite", "sqlalchemy"])
def history_store(request, sqlite_store, sqlalchemy_store):
    if request.param == "sqlite":
        return sqlite_store
    return sqlalchemy_store


class TestHistoryStoreContract:
    """Behavior that every HistoryStoreBase implementation must match."""

    def test_is_history_store(self, history_store):
        assert isinstance(history_store, HistoryStoreBase)

    def test_add_and_get_history(self, history_store):
        memory_id = str(uuid.uuid4())
        created_at = datetime.now().isoformat()
        history_store.add_history(
            memory_id=memory_id,
            old_memory=None,
            new_memory="hello",
            event="ADD",
            created_at=created_at,
            actor_id="user-1",
            role="user",
        )
        rows = history_store.get_history(memory_id)
        assert len(rows) == 1
        assert rows[0]["memory_id"] == memory_id
        assert rows[0]["new_memory"] == "hello"
        assert rows[0]["event"] == "ADD"
        assert rows[0]["actor_id"] == "user-1"
        assert rows[0]["role"] == "user"
        assert rows[0]["is_deleted"] is False

    def test_batch_add_history(self, history_store):
        memory_id = str(uuid.uuid4())
        history_store.batch_add_history(
            [
                {
                    "memory_id": memory_id,
                    "old_memory": None,
                    "new_memory": "one",
                    "event": "ADD",
                    "created_at": "2026-01-01T00:00:00",
                },
                {
                    "memory_id": memory_id,
                    "old_memory": "one",
                    "new_memory": "two",
                    "event": "UPDATE",
                    "created_at": "2026-01-01T00:00:01",
                    "updated_at": "2026-01-01T00:00:01",
                },
            ]
        )
        rows = history_store.get_history(memory_id)
        assert [r["event"] for r in rows] == ["ADD", "UPDATE"]
        assert [r["new_memory"] for r in rows] == ["one", "two"]

    def test_get_history_empty(self, history_store):
        assert history_store.get_history("missing") == []

    def test_save_and_get_messages(self, history_store):
        scope = f"user:{uuid.uuid4()}"
        history_store.save_messages(
            [
                {"role": "user", "content": "hi", "name": None},
                {"role": "assistant", "content": "hello", "name": "bot"},
            ],
            scope,
        )
        rows = history_store.get_last_messages(scope, limit=10)
        assert len(rows) == 2
        assert rows[0]["role"] == "user"
        assert rows[0]["content"] == "hi"
        assert rows[1]["role"] == "assistant"
        assert rows[1]["name"] == "bot"

    def test_save_messages_keeps_latest_ten(self, history_store):
        scope = f"user:{uuid.uuid4()}"
        for i in range(12):
            history_store.save_messages([{"role": "user", "content": f"m{i}", "name": None}], scope)
        rows = history_store.get_last_messages(scope, limit=10)
        assert len(rows) == 10
        assert [r["content"] for r in rows] == [f"m{i}" for i in range(2, 12)]

    def test_reset_and_recreate(self, history_store):
        memory_id = str(uuid.uuid4())
        history_store.add_history(memory_id, None, "x", "ADD")
        history_store.save_messages([{"role": "user", "content": "hi", "name": None}], "s1")
        history_store.reset()
        # reset drops tables; a fresh instance of the same backend recreates them.
        if isinstance(history_store, SQLiteManager):
            replacement = SQLiteManager(history_store.db_path)
        else:
            # In-memory sqlite via SQLAlchemy is gone after DROP; reopen a new store.
            replacement = PostgresHistoryStore("sqlite:///:memory:")
        try:
            assert replacement.get_history(memory_id) == []
            assert replacement.get_last_messages("s1") == []
        finally:
            replacement.close()


class TestHistoryStoreFactory:
    def test_default_memory_config_uses_sqlite(self, tmp_path):
        config = _memory_config(history_db_path=str(tmp_path / "history.db"))
        store = HistoryStoreFactory.from_memory_config(config)
        try:
            assert isinstance(store, SQLiteManager)
            assert store.db_path == str(tmp_path / "history.db")
        finally:
            store.close()

    def test_explicit_sqlite_provider(self, tmp_path):
        config = _memory_config(history_store={"provider": "sqlite", "config": {"path": str(tmp_path / "custom.db")}})
        store = HistoryStoreFactory.from_memory_config(config)
        try:
            assert isinstance(store, SQLiteManager)
            assert store.db_path.endswith("custom.db")
        finally:
            store.close()

    def test_postgres_provider_with_sqlite_url(self):
        config = _memory_config(history_store={"provider": "postgres", "config": {"url": "sqlite:///:memory:"}})
        store = HistoryStoreFactory.from_memory_config(config)
        try:
            assert isinstance(store, PostgresHistoryStore)
            store.add_history("m1", None, "n", "ADD")
            assert store.get_history("m1")[0]["new_memory"] == "n"
        finally:
            store.close()

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unsupported history store provider"):
            HistoryStoreFactory.create("redis", {})

    def test_postgres_config_requires_url(self):
        with pytest.raises(ValueError, match="config.url"):
            HistoryStoreConfig(provider="postgres", config={})
