"""Tests for server.db._build_database_url SSL mode handling (salvage of #5374)."""
import importlib
import os
from unittest.mock import patch

import pytest

pytest.importorskip("sqlalchemy", reason="sqlalchemy not installed")


def _build_url(env):
    base = {
        "POSTGRES_HOST": "h",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "u",
        "POSTGRES_PASSWORD": "p",
        "APP_DB_NAME": "appdb",
    }
    base.update(env)
    with patch.dict(os.environ, base, clear=False):
        # Avoid actually creating the engine at import time.
        with patch("sqlalchemy.create_engine"):
            import server.db as server_db
            importlib.reload(server_db)
            return server_db._build_database_url()


def test_no_sslmode_omits_query_string():
    # ensure POSTGRES_SSLMODE absent
    with patch.dict(os.environ, {}, clear=False):
        os.environ.pop("POSTGRES_SSLMODE", None)
        url = _build_url({})
    assert url == "postgresql+psycopg://u:p@h:5432/appdb"
    assert "sslmode" not in url


def test_sslmode_appended_when_set():
    url = _build_url({"POSTGRES_SSLMODE": "require"})
    assert url == "postgresql+psycopg://u:p@h:5432/appdb?sslmode=require"
