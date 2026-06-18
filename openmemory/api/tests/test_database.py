"""Tests for dialect-conditional database engine (task_01)."""


import pytest
from sqlalchemy import create_engine

from app.database import (
    DATABASE_URL,
    engine_connect_args,
    is_postgresql,
    is_sqlite,
)


class TestDialectHelpers:
    def test_sqlite_url_detected(self):
        assert is_sqlite("sqlite:///./openmemory.db")
        assert not is_postgresql("sqlite:///./openmemory.db")

    def test_postgresql_url_detected(self):
        assert is_postgresql("postgresql://mem0:mem0@pgbouncer:5432/openmemory")
        assert not is_sqlite("postgresql://mem0:mem0@pgbouncer:5432/openmemory")

    def test_sqlite_connect_args_include_check_same_thread(self):
        args = engine_connect_args("sqlite:///./x.db")
        assert args == {"check_same_thread": False}

    def test_postgresql_connect_args_empty(self):
        assert engine_connect_args("postgresql://u:p@h/db") == {}


class TestEngineCreation:
    def test_sqlite_engine_accepts_multithreaded_access(self, tmp_path):
        path = tmp_path / "t.db"
        eng = create_engine(
            f"sqlite:///{path}",
            connect_args=engine_connect_args(f"sqlite:///{path}"),
        )
        with eng.connect() as conn:
            assert conn.execute(__import__("sqlalchemy").text("SELECT 1")).scalar() == 1
        eng.dispose()

    def test_empty_database_url_raises(self, monkeypatch):
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DATABASE_URL", "")
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            import importlib
            import app.database as db_mod

            importlib.reload(db_mod)

    def test_module_engine_uses_current_database_url(self):
        assert DATABASE_URL
        assert engine_connect_args() == (
            {"check_same_thread": False} if is_sqlite() else {}
        )
