from unittest.mock import MagicMock

import pytest

from mem0.vector_stores.cassandra import CassandraDB
from mem0.vector_stores.pinecone import PineconeDB


@pytest.fixture
def mock_cassandra_client():
    client = MagicMock()
    client.Index.return_value = MagicMock()
    client.list_indexes.return_value.names.return_value = []
    return client


@pytest.fixture
def cassandra_db(mock_cassandra_client):
    return CassandraDB(
        "ks",
        "table",
        "user",
        "password",
        1024
    )


def test_create_col_existing_index(mock_cassandra_client):
    # Set up the mock before creating the PineconeDB object
    mock_cassandra_client.list_indexes.return_value.names.return_value = ["test_index"]

    cassandra_db = CassandraDB(
        "ks",
        "table",
        "user",
        "password",
        1024
    )

    # Reset the mock to verify it wasn't called during the test
    mock_cassandra_client.create_index.reset_mock()

    cassandra_db.create_col(128, "cosine")

    mock_cassandra_client.create_index.assert_not_called()


def test_create_col_new_index(cassandra_db, mock_cassandra_client):
    mock_cassandra_client.list_indexes.return_value.names.return_value = []
    cassandra_db.create_col(128, "cosine")
    mock_cassandra_client.create_index.assert_called()


def test_insert_vectors(mock_cassandra_client):
    vectors = [[0.1] * 128, [0.2] * 128]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]
    mock_cassandra_client.insert(vectors, payloads, ids)
    mock_cassandra_client.index.upsert.assert_called()


def test_search_vectors(cassandra_db):
    cassandra_db.index.query.return_value.matches = [{"id": "id1", "score": 0.9, "metadata": {"name": "vector1"}}]
    results = cassandra_db.search("test query", [0.1] * 128, limit=1)
    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].score == 0.9


def test_update_vector(cassandra_db):
    cassandra_db.update("id1", vector=[0.5] * 128, payload={"name": "updated"})
    cassandra_db.index.upsert.assert_called()


def test_delete_vector(cassandra_db):
    cassandra_db.delete("id1")
    cassandra_db.index.delete.assert_called_with(ids=["id1"])


def test_get_vector_not_found(cassandra_db):
    cassandra_db.index.fetch.return_value.vectors = {}
    result = cassandra_db.get("id1")
    assert result is None

def test_delete_col(cassandra_db):
    cassandra_db.delete_col()
    cassandra_db.client.delete_index.assert_called_with("test_index")


def test_col_info(cassandra_db):
    cassandra_db.col_info()
    cassandra_db.client.describe_index.assert_called_with("test_index")
