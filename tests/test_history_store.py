from types import SimpleNamespace

from mem0.memory import storage


def test_create_history_manager_sqlite():
    config = SimpleNamespace(history_db_provider="sqlite", history_db_path=":memory:")
    manager = storage.create_history_manager(config)
    assert isinstance(manager, storage.SQLiteManager)


def test_create_history_manager_postgres(monkeypatch):
    created = {}

    class DummyPostgresManager:
        def __init__(self, dsn, table_name):
            created["dsn"] = dsn
            created["table"] = table_name

    monkeypatch.setattr(storage, "PostgresHistoryManager", DummyPostgresManager)

    config = SimpleNamespace(
        history_db_provider="postgres",
        history_db_url="postgresql://user:pass@host:5432/db",
        history_db_table="history_test",
    )

    manager = storage.create_history_manager(config)

    assert isinstance(manager, DummyPostgresManager)
    assert created["dsn"] == "postgresql://user:pass@host:5432/db"
    assert created["table"] == "history_test"
