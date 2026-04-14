import os
import tempfile
import uuid

import pytest

from mem0.configs.base import HistoryStoreConfig, MemoryConfig
from mem0.memory.storage_base import HistoryStoreBase
from mem0.memory.storage_noop import NoopHistoryStore
from mem0.utils.factory import HistoryStoreFactory


class TestHistoryStoreBase:
    """Test that the abstract base class enforces the interface."""

    def test_cannot_instantiate_base(self):
        with pytest.raises(TypeError):
            HistoryStoreBase()


class TestNoopHistoryStore:
    """Test the no-op history store."""

    @pytest.fixture
    def store(self):
        return NoopHistoryStore()

    def test_add_history_does_nothing(self, store):
        store.add_history(
            memory_id="m1",
            old_memory=None,
            new_memory="hello",
            event="ADD",
            created_at="2026-01-01T00:00:00",
        )

    def test_get_history_returns_empty(self, store):
        assert store.get_history("m1") == []

    def test_reset_does_nothing(self, store):
        store.reset()

    def test_close_does_nothing(self, store):
        store.close()

    def test_is_instance_of_base(self, store):
        assert isinstance(store, HistoryStoreBase)


class TestHistoryStoreConfig:
    """Test the HistoryStoreConfig model."""

    def test_default_values(self):
        config = HistoryStoreConfig()
        assert config.provider == "sqlite"
        assert config.config is None

    def test_custom_provider(self):
        config = HistoryStoreConfig(provider="postgres", config={"url": "postgresql://localhost/test"})
        assert config.provider == "postgres"
        assert config.config["url"] == "postgresql://localhost/test"

    def test_noop_provider(self):
        config = HistoryStoreConfig(provider="noop")
        assert config.provider == "noop"


class TestMemoryConfigBackwardCompat:
    """Test backward compatibility of MemoryConfig with history_db_path."""

    def test_legacy_history_db_path(self):
        config = MemoryConfig(history_db_path="/tmp/test_history.db")
        assert config.history_store is not None
        assert config.history_store.provider == "sqlite"
        assert config.history_store.config == {"db_path": "/tmp/test_history.db"}

    def test_default_creates_sqlite(self):
        config = MemoryConfig()
        assert config.history_store is not None
        assert config.history_store.provider == "sqlite"
        assert config.history_store.config is not None

    def test_disable_history(self):
        config = MemoryConfig(disable_history=True)
        assert config.history_store is not None
        assert config.history_store.provider == "noop"

    def test_explicit_history_store(self):
        config = MemoryConfig(history_store={"provider": "postgres", "config": {"url": "postgresql://localhost/test"}})
        assert config.history_store.provider == "postgres"
        assert config.history_store.config["url"] == "postgresql://localhost/test"

    def test_explicit_history_store_takes_precedence(self):
        config = MemoryConfig(
            history_db_path="/tmp/ignored.db",
            history_store={"provider": "noop"},
        )
        assert config.history_store.provider == "noop"

    def test_disable_history_takes_precedence_over_path(self):
        config = MemoryConfig(
            history_db_path="/tmp/ignored.db",
            disable_history=True,
        )
        assert config.history_store.provider == "noop"


class TestHistoryStoreFactory:
    """Test the HistoryStoreFactory."""

    def test_create_sqlite(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as f:
            db_path = f.name
        try:
            store = HistoryStoreFactory.create("sqlite", {"db_path": db_path})
            assert isinstance(store, HistoryStoreBase)
            store.close()
        finally:
            os.unlink(db_path)

    def test_create_sqlite_default(self):
        store = HistoryStoreFactory.create("sqlite", {"db_path": ":memory:"})
        assert isinstance(store, HistoryStoreBase)
        store.close()

    def test_create_noop(self):
        store = HistoryStoreFactory.create("noop")
        assert isinstance(store, NoopHistoryStore)

    def test_create_invalid_provider(self):
        with pytest.raises(ValueError, match="Unsupported history store provider"):
            HistoryStoreFactory.create("redis")

    def test_noop_roundtrip(self):
        store = HistoryStoreFactory.create("noop")
        memory_id = str(uuid.uuid4())
        store.add_history(memory_id=memory_id, old_memory=None, new_memory="test", event="ADD")
        assert store.get_history(memory_id) == []
        store.reset()
        store.close()

    def test_sqlite_roundtrip(self):
        store = HistoryStoreFactory.create("sqlite", {"db_path": ":memory:"})
        memory_id = str(uuid.uuid4())
        store.add_history(
            memory_id=memory_id,
            old_memory=None,
            new_memory="test memory",
            event="ADD",
            created_at="2026-01-01T00:00:00",
        )
        history = store.get_history(memory_id)
        assert len(history) == 1
        assert history[0]["memory_id"] == memory_id
        assert history[0]["new_memory"] == "test memory"
        assert history[0]["event"] == "ADD"
        store.close()

    def test_create_postgres(self):
        """Test creating a 'postgres' provider (uses SQLAlchemy, tested with in-memory SQLite)."""
        store = HistoryStoreFactory.create("postgres", {"url": "sqlite://"})
        assert isinstance(store, HistoryStoreBase)
        store.close()

    def test_postgres_roundtrip(self):
        """Test full roundtrip with the postgres provider (SQLAlchemy-based, in-memory SQLite)."""
        store = HistoryStoreFactory.create("postgres", {"url": "sqlite://"})
        memory_id = str(uuid.uuid4())
        store.add_history(
            memory_id=memory_id,
            old_memory=None,
            new_memory="sqlalchemy test",
            event="ADD",
            created_at="2026-01-01T00:00:00",
            actor_id="test_actor",
            role="user",
        )
        history = store.get_history(memory_id)
        assert len(history) == 1
        assert history[0]["memory_id"] == memory_id
        assert history[0]["new_memory"] == "sqlalchemy test"
        assert history[0]["event"] == "ADD"
        assert history[0]["actor_id"] == "test_actor"
        assert history[0]["role"] == "user"
        assert history[0]["is_deleted"] is False

        # Test reset
        store.reset()
        assert store.get_history(memory_id) == []
        store.close()
