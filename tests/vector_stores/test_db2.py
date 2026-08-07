import json
import os
from unittest.mock import MagicMock, patch

import pytest

from mem0.vector_stores.db2 import Db2VectorStore, OutputData

# MOCK TESTS (run when NOT live)

@pytest.fixture
def mock_ibm_db():
    with patch("ibm_db_dbi.connect") as mock_connect, patch("ibm_db.connect") as mock_ibm:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor

@pytest.fixture
def db2_store(mock_ibm_db):
    return Db2VectorStore(
        connection_params={
            "database": "testdb",
            "host": "localhost",
            "port": 50000,
            "username": "user",
            "password": "pwd"
        }
    )

def test_init_with_connection_params(mock_ibm_db):
    mock_conn, _ = mock_ibm_db
    store = Db2VectorStore(
        connection_params={
            "database": "testdb",
            "host": "localhost",
            "port": 50000,
            "username": "user",
            "password": "pwd"
        }
    )
    assert store.table_name == "mem0"
    assert store.distance_strategy == "COSINE"

def test_init_with_client():
    mock_client = MagicMock()
    store = Db2VectorStore(client=mock_client)
    assert store.conn == mock_client

def test_ensure_collection(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    mock_cursor.fetchall.return_value = []
    
    db2_store._ensure_collection(1536)
    
    # Should create table
    assert mock_cursor.execute.call_count >= 2

def test_insert(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True  # skip ensure for pure unit test
    
    vectors = [[1.0, 2.0], [3.0, 4.0]]
    payloads = [{"meta": "1"}, {"meta": "2"}]
    ids = ["id1", "id2"]
    
    db2_store.insert(vectors, payloads, ids)
    assert mock_cursor.execute.call_count == 2
    args1, _ = mock_cursor.execute.call_args_list[0]
    assert "INSERT INTO mem0" in args1[0]

def test_search(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    
    # Mock search results: (id, metadata_str, dist)
    mock_cursor.fetchall.return_value = [
        ("id1", '{"meta": "1"}', 0.1),
        ("id2", '{"meta": "2"}', 0.2)
    ]
    
    results = db2_store.search("query", [1.0, 2.0], top_k=2)
    
    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.9  # 1.0 - 0.1 (Cosine)

def test_search_with_filters(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    mock_cursor.fetchall.return_value = []
    
    db2_store.search("query", [1.0, 2.0], filters={"source": "docs"})
    
    args, _ = mock_cursor.execute.call_args_list[0]
    query_str = args[0]
    assert "JSON_VALUE" in query_str
    assert "$.\"source\"" in query_str

def test_delete(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    
    db2_store.delete("id1")
    
    args, _ = mock_cursor.execute.call_args_list[0]
    assert "DELETE FROM mem0" in args[0]

def test_update(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    
    db2_store.update("id1", vector=[1.1, 2.2], payload={"meta": "new"})
    
    args, _ = mock_cursor.execute.call_args_list[0]
    assert "UPDATE mem0" in args[0]

def test_get(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    
    mock_cursor.fetchone.return_value = ("id1", '{"meta": "1"}')
    
    result = db2_store.get("id1")
    assert result.id == "id1"
    assert result.payload == {"meta": "1"}

def test_list(db2_store, mock_ibm_db):
    _, mock_cursor = mock_ibm_db
    db2_store._collection_ensured = True
    
    mock_cursor.fetchall.return_value = [
        ("id1", '{"meta": "1"}'),
        ("id2", '{"meta": "2"}')
    ]
    
    results = db2_store.list()
    assert len(results) == 2
    assert results[0].id == "id1"

# LIVE TESTS (skipped if DB2_HOST is not set)
db2_host = os.getenv("DB2_HOST")
pytestmark = pytest.mark.skipif(not db2_host, reason="DB2_HOST not set, skipping live tests")

@pytest.fixture
def live_db2_store():
    store = Db2VectorStore(
        connection_params={
            "database": os.getenv("DB2_DATABASE", "testdb"),
            "host": os.getenv("DB2_HOST", "localhost"),
            "port": int(os.getenv("DB2_PORT", 50000)),
            "username": os.getenv("DB2_USERNAME", "user"),
            "password": os.getenv("DB2_PASSWORD", "pwd")
        },
        table_name="test_mem0_live"
    )
    yield store
    # Cleanup
    try:
        store.delete_col()
    except Exception:
        pass

def test_live_insert_and_search(live_db2_store):
    live_db2_store.insert([[1.0, 2.0]], [{"src": "a"}], ["1"])
    results = live_db2_store.search("q", [1.0, 2.0])
    assert len(results) == 1
    assert results[0].id == "1"
