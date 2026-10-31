"""PGVector lifecycle must release owned connection pools and leave borrowed ones open."""

from unittest.mock import MagicMock

import pytest

from mem0.vector_stores import pgvector as pgvector_module
from mem0.vector_stores.pgvector import PGVector


@pytest.fixture
def pools(monkeypatch):
    """Replace the driver pool class so constructing a store touches no database."""
    created = []

    def make_pool(*args, **kwargs):
        pool = MagicMock()
        created.append(pool)
        return pool

    monkeypatch.setattr(pgvector_module, "ConnectionPool", make_pool)
    return created


def make_store(**kwargs):
    defaults = {
        "collection_name": "test_collection",
        "embedding_model_dims": 1536,
        "dbname": "test_db",
        "user": "user",
        "password": "password",
        "host": "localhost",
        "port": 5432,
        "diskann": False,
        "hnsw": False,
    }
    defaults.update(kwargs)
    return PGVector(**defaults)


def test_close_closes_owned_pool(pools, monkeypatch):
    monkeypatch.setattr(pgvector_module, "PSYCOPG_VERSION", 3)
    store = make_store()

    store.close()

    pools[0].close.assert_called_once()
    pools[0].closeall.assert_not_called()


def test_close_closes_owned_pool_psycopg2(pools, monkeypatch):
    monkeypatch.setattr(pgvector_module, "PSYCOPG_VERSION", 2)
    store = make_store()

    store.close()

    pools[0].closeall.assert_called_once()
    pools[0].close.assert_not_called()


def test_close_is_idempotent(pools, monkeypatch):
    monkeypatch.setattr(pgvector_module, "PSYCOPG_VERSION", 3)
    store = make_store()

    store.close()
    store.close()

    pools[0].close.assert_called_once()


def test_close_leaves_borrowed_pool_open(pools):
    borrowed = MagicMock()
    store = make_store(connection_pool=borrowed)

    store.close()
    store.__del__()

    borrowed.close.assert_not_called()
    borrowed.closeall.assert_not_called()


def test_del_closes_owned_pool_once(pools, monkeypatch):
    monkeypatch.setattr(pgvector_module, "PSYCOPG_VERSION", 3)
    store = make_store()

    store.__del__()
    store.__del__()

    pools[0].close.assert_called_once()
