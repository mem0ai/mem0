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


def test_search_vectors_with_filters(chromadb_instance, mock_chromadb_client):
    """Test search with agent_id and run_id filters."""
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1", "user_id": "alice", "agent_id": "agent1", "run_id": "run1"}]],
    }
    chromadb_instance.collection.query.return_value = mock_result

    vectors = [[0.1, 0.2, 0.3]]
    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = chromadb_instance.search(query="", vectors=vectors, limit=2, filters=filters)

    # Verify that _generate_where_clause was called with the filters
    expected_where = {"$and": [{"user_id": "alice"}, {"agent_id": "agent1"}, {"run_id": "run1"}]}
    chromadb_instance.collection.query.assert_called_once_with(
        query_embeddings=vectors, where=expected_where, n_results=2
    )

    assert len(results) == 1
    assert results[0].id == "id1"
    assert results[0].payload["user_id"] == "alice"
    assert results[0].payload["agent_id"] == "agent1"
    assert results[0].payload["run_id"] == "run1"


def test_search_vectors_with_single_filter(chromadb_instance, mock_chromadb_client):
    """Test search with single filter (should not use $and)."""
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1", "user_id": "alice"}]],
    }
    chromadb_instance.collection.query.return_value = mock_result

    vectors = [[0.1, 0.2, 0.3]]
    filters = {"user_id": "alice"}
    results = chromadb_instance.search(query="", vectors=vectors, limit=2, filters=filters)

    # Verify that single filter is passed as-is (no $and wrapper)
    chromadb_instance.collection.query.assert_called_once_with(
        query_embeddings=vectors, where=filters, n_results=2
    )

    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"


def test_search_vectors_with_no_filters(chromadb_instance, mock_chromadb_client):
    """Test search with no filters."""
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1"}]],
    }
    chromadb_instance.collection.query.return_value = mock_result

    vectors = [[0.1, 0.2, 0.3]]
    results = chromadb_instance.search(query="", vectors=vectors, limit=2, filters=None)

    chromadb_instance.collection.query.assert_called_once_with(
        query_embeddings=vectors, where=None, n_results=2
    )

    assert len(results) == 1


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


def test_list_vectors_with_filters(chromadb_instance):
    """Test list with agent_id and run_id filters."""
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1", "user_id": "alice", "agent_id": "agent1", "run_id": "run1"}]],
    }
    chromadb_instance.collection.get.return_value = mock_result

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = chromadb_instance.list(filters=filters, limit=2)

    # Verify that _generate_where_clause was called with the filters
    expected_where = {"$and": [{"user_id": "alice"}, {"agent_id": "agent1"}, {"run_id": "run1"}]}
    chromadb_instance.collection.get.assert_called_once_with(where=expected_where, limit=2)

    assert len(results[0]) == 1
    assert results[0][0].payload["user_id"] == "alice"
    assert results[0][0].payload["agent_id"] == "agent1"
    assert results[0][0].payload["run_id"] == "run1"


def test_list_vectors_with_single_filter(chromadb_instance):
    """Test list with single filter (should not use $and)."""
    mock_result = {
        "ids": [["id1"]],
        "distances": [[0.1]],
        "metadatas": [[{"name": "vector1", "user_id": "alice"}]],
    }
    chromadb_instance.collection.get.return_value = mock_result

    filters = {"user_id": "alice"}
    results = chromadb_instance.list(filters=filters, limit=2)

    # Verify that single filter is passed as-is (no $and wrapper)
    chromadb_instance.collection.get.assert_called_once_with(where=filters, limit=2)

    assert len(results[0]) == 1
    assert results[0][0].payload["user_id"] == "alice"


def test_generate_where_clause_multiple_filters():
    """Test _generate_where_clause with multiple filters."""
    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    result = ChromaDB._generate_where_clause(filters)
    
    expected = {"$and": [{"user_id": "alice"}, {"agent_id": "agent1"}, {"run_id": "run1"}]}
    assert result == expected


def test_generate_where_clause_single_filter():
    """Test _generate_where_clause with single filter."""
    filters = {"user_id": "alice"}
    result = ChromaDB._generate_where_clause(filters)
    
    # Single filter should be returned as-is
    assert result == filters


def test_generate_where_clause_no_filters():
    """Test _generate_where_clause with no filters."""
    result = ChromaDB._generate_where_clause(None)
    assert result == {}

    result = ChromaDB._generate_where_clause({})
    assert result == {}


def test_generate_where_clause_non_string_values():
    """Test _generate_where_clause with non-string values."""
    filters = {"user_id": "alice", "count": 5, "active": True}
    result = ChromaDB._generate_where_clause(filters)
    
    # Only string values should be included in $and array
    expected = {"$and": [{"user_id": "alice"}]}
    assert result == expected
