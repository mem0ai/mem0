from unittest.mock import Mock, patch

import pytest

from mem0.vector_stores.chroma import ChromaDB


@pytest.fixture
def mock_chromadb_client():
    with patch("chromadb.Client") as mock_client:
        yield mock_client


@pytest.fixture
def chromadb_instance(mock_chromadb_client):
    mock_collection = Mock()
    mock_chromadb_client.return_value.get_or_create_collection.return_value = mock_collection

    return ChromaDB(collection_name="test_collection", client=mock_chromadb_client.return_value)


def test_insert_vectors(chromadb_instance, mock_chromadb_client):
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"name": "vector1"}, {"name": "vector2"}]
    ids = ["id1", "id2"]

    chromadb_instance.insert(vectors=vectors, payloads=payloads, ids=ids)

    chromadb_instance.collection.add.assert_called_once_with(ids=ids, embeddings=vectors, metadatas=payloads)


def test_search_vectors(chromadb_instance, mock_chromadb_client):
    mock_result = {
        "ids": [["id1", "id2"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [[{"name": "vector1"}, {"name": "vector2"}]],
    }
    chromadb_instance.collection.query.return_value = mock_result

    vectors = [[0.1, 0.2, 0.3]]
    results = chromadb_instance.search(query="", vectors=vectors, limit=2)

    chromadb_instance.collection.query.assert_called_once_with(query_embeddings=vectors, where=None, n_results=2)

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].score == 0.1
    assert results[0].payload == {"name": "vector1"}


def test_delete_vector(chromadb_instance):
    vector_id = "id1"

    chromadb_instance.delete(vector_id=vector_id)

    chromadb_instance.collection.delete.assert_called_once_with(ids=vector_id)


def test_update_vector(chromadb_instance):
    vector_id = "id1"
    new_vector = [0.7, 0.8, 0.9]
    new_payload = {"name": "updated_vector"}

    chromadb_instance.update(vector_id=vector_id, vector=new_vector, payload=new_payload)

    chromadb_instance.collection.update.assert_called_once_with(
        ids=vector_id, embeddings=new_vector, metadatas=new_payload
    )


def test_get_vector(chromadb_instance):
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1"}]],
    }
    chromadb_instance.collection.get.return_value = mock_result

    result = chromadb_instance.get(vector_id="id1")

    chromadb_instance.collection.get.assert_called_once_with(ids=["id1"])

    assert result.id == "id1"
    assert result.score == 0.1
    assert result.payload == {"name": "vector1"}


def test_list_vectors(chromadb_instance):
    mock_result = {
        "ids": [["id1", "id2"]],
        "distances": [[0.1, 0.2]],
        "metadatas": [[{"name": "vector1"}, {"name": "vector2"}]],
    }
    chromadb_instance.collection.get.return_value = mock_result

    results = chromadb_instance.list(limit=2)

    chromadb_instance.collection.get.assert_called_once_with(where=None, limit=2)

    assert len(results[0]) == 2
    assert results[0][0].id == "id1"
    assert results[0][1].id == "id2"
