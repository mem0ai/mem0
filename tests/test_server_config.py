import importlib
import os
from unittest.mock import patch

import pytest

pytest.importorskip("fastapi", reason="fastapi not installed")


@pytest.fixture(autouse=True)
def mock_db_dependencies():
    """Mock sqlalchemy create_engine globally to avoid loading psycopg dialect."""
    with patch("sqlalchemy.create_engine") as mock_create:
        yield mock_create


def test_build_database_url_without_sslmode():
    env_mock = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpassword",
        "APP_DB_NAME": "testdb",
    }
    with patch.dict(os.environ, env_mock, clear=True):
        import server.db as server_db
        importlib.reload(server_db)
        url = server_db._build_database_url()
        assert "sslmode" not in url
        assert url == "postgresql+psycopg://testuser:testpassword@localhost:5432/testdb"


def test_build_database_url_with_sslmode():
    env_mock = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "testuser",
        "POSTGRES_PASSWORD": "testpassword",
        "APP_DB_NAME": "testdb",
        "POSTGRES_SSLMODE": "require",
    }
    with patch.dict(os.environ, env_mock, clear=True):
        import server.db as server_db
        importlib.reload(server_db)
        url = server_db._build_database_url()
        assert "?sslmode=require" in url
        assert url == "postgresql+psycopg://testuser:testpassword@localhost:5432/testdb?sslmode=require"


def test_server_main_config_sslmode():
    env_mock = {
        "OPENAI_API_KEY": "fake-key",
        "ADMIN_API_KEY": "admin-key",
        "POSTGRES_SSLMODE": "prefer",
        "AUTH_DISABLED": "true",
    }
    # Mock Memory.from_config so server/main doesn't try to instantiate a real memory object
    with patch("mem0.Memory.from_config"):
        with patch.dict(os.environ, env_mock):
            import server.main as server_main
            importlib.reload(server_main)
            
            # Verify the global variable is set
            assert server_main.POSTGRES_SSLMODE == "prefer"
            
            # Verify the DEFAULT_CONFIG contains sslmode
            pg_config = server_main.DEFAULT_CONFIG["vector_store"]["config"]
            assert pg_config["sslmode"] == "prefer"
