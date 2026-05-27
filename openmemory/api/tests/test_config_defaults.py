import importlib
import sys

import pytest


pytest.importorskip("openai")


def test_sqlite_database_uses_check_same_thread(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./openmemory.db")
    sys.modules.pop("app.database", None)

    import app.database as database  # noqa: WPS433

    database = importlib.reload(database)
    assert database.engine.url.drivername == "sqlite"


def test_postgres_database_does_not_use_sqlite_connect_args(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql+psycopg2://user:pass@localhost:5432/openmemory",
    )
    sys.modules.pop("app.database", None)

    import app.database as database  # noqa: WPS433

    database = importlib.reload(database)
    assert database.engine.url.drivername == "postgresql+psycopg2"


@pytest.mark.parametrize(
    ("host", "port", "expected_host", "expected_port"),
    [
        ("qdrant", "6333", "qdrant", 6333),
        (None, None, "qdrant", 6333),
    ],
)
def test_qdrant_default_host_is_compose_service_name(
    monkeypatch,
    host,
    port,
    expected_host,
    expected_port,
):
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    if host is None:
        monkeypatch.delenv("QDRANT_HOST", raising=False)
    else:
        monkeypatch.setenv("QDRANT_HOST", host)

    if port is None:
        monkeypatch.delenv("QDRANT_PORT", raising=False)
    else:
        monkeypatch.setenv("QDRANT_PORT", port)

    from app.utils.memory import get_default_memory_config

    config = get_default_memory_config()
    assert config["vector_store"]["provider"] == "qdrant"
    assert config["vector_store"]["config"]["host"] == expected_host
    assert config["vector_store"]["config"]["port"] == expected_port