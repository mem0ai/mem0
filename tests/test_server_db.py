import os
from unittest.mock import patch

from server.db import _build_database_url


def test_build_database_url_from_individual_components_with_ssl():
    """Verify that individual components are parsed and combined correctly with SSL."""
    env = {
        "POSTGRES_HOST": "pooled.db.prisma.io",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "some_user",
        "POSTGRES_PASSWORD": "password123",
        "POSTGRES_SSLMODE": "require",
    }
    with patch.dict(os.environ, env, clear=True):
        url = _build_database_url()
        assert url == "postgresql+psycopg://some_user:password123@pooled.db.prisma.io:5432/mem0_app?sslmode=require"


def test_build_database_url_defaults():
    """Verify that APP_DB_NAME defaults to 'mem0_app' when not set, and custom value works."""
    env = {
        "POSTGRES_HOST": "localhost",
        "POSTGRES_PORT": "5432",
        "POSTGRES_USER": "postgres",
        "POSTGRES_PASSWORD": "password",
    }
    with patch.dict(os.environ, env, clear=True):
        url = _build_database_url()
        assert url == "postgresql+psycopg://postgres:password@localhost:5432/mem0_app"

    # With APP_DB_NAME custom value
    env["APP_DB_NAME"] = "override_app_db"
    with patch.dict(os.environ, env, clear=True):
        url = _build_database_url()
        assert url == "postgresql+psycopg://postgres:password@localhost:5432/override_app_db"


if __name__ == "__main__":
    print("Running server DB URL tests...")
    test_build_database_url_from_individual_components_with_ssl()
    test_build_database_url_defaults()
    print("All tests passed successfully!")

