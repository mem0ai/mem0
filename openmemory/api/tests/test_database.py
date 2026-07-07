import importlib
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import sqlalchemy


API_ROOT = Path(__file__).resolve().parents[1]
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))


def _import_database_with_url(monkeypatch, database_url):
    sys.modules.pop("app.database", None)
    captured = {}

    def fake_create_engine(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return Mock(name="engine")

    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setattr(sqlalchemy, "create_engine", fake_create_engine)

    try:
        importlib.import_module("app.database")
    finally:
        sys.modules.pop("app.database", None)
    return captured


@pytest.mark.parametrize(
    "database_url",
    [
        "sqlite:///./openmemory.db",
        "sqlite+pysqlite:///./openmemory.db",
    ],
)
def test_sqlite_database_urls_keep_sqlite_thread_connect_arg(monkeypatch, database_url):
    captured = _import_database_with_url(monkeypatch, database_url)

    assert captured["url"] == database_url
    assert captured["kwargs"]["connect_args"] == {"check_same_thread": False}


def test_non_sqlite_database_url_does_not_get_sqlite_connect_arg(monkeypatch):
    captured = _import_database_with_url(
        monkeypatch,
        "postgresql+psycopg2://user:pass@localhost:5432/openmemory",
    )

    assert captured["url"] == "postgresql+psycopg2://user:pass@localhost:5432/openmemory"
    assert "connect_args" not in captured["kwargs"]
