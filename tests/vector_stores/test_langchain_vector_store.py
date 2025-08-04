from unittest.mock import Mock, patch

import pytest
from langchain_community.vectorstores import VectorStore

from mem0.vector_stores.langchain import Langchain


@pytest.fixture
def mock_langchain_client():
    with patch("langchain_community.vectorstores.VectorStore") as mock_client:
        yield mock_client


@pytest.fixture
def langchain_instance(mock_langchain_client):
    mock_client = Mock(spec=VectorStore)
    return Langchain(client=mock_client, collection_name="test_collection")


def test_insert_vectors(langchain_instance):
    # Test data
    vectors = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    payloads = [{"data": "text1", "name": "vector1"}, {"data": "text2", "name": "vector2"}]
    ids = ["id1", "id2"]

    # Test with add_embeddings method
    langchain_instance.client.add_embeddings = Mock()
    langchain_instance.insert(vectors=vectors, payloads=payloads, ids=ids)
    langchain_instance.client.add_embeddings.assert_called_once_with(embeddings=vectors, metadatas=payloads, ids=ids)

    # Test with add_texts method
    delattr(langchain_instance.client, "add_embeddings")  # Remove attribute completely
    langchain_instance.client.add_texts = Mock()
    langchain_instance.insert(vectors=vectors, payloads=payloads, ids=ids)
    langchain_instance.client.add_texts.assert_called_once_with(texts=["text1", "text2"], metadatas=payloads, ids=ids)

    # Test with empty payloads
    langchain_instance.client.add_texts.reset_mock()
    langchain_instance.insert(vectors=vectors, payloads=None, ids=ids)
    langchain_instance.client.add_texts.assert_called_once_with(texts=["", ""], metadatas=None, ids=ids)


def test_search_vectors(langchain_instance):
    # Mock search results
    mock_docs = [Mock(metadata={"name": "vector1"}, id="id1"), Mock(metadata={"name": "vector2"}, id="id2")]
    langchain_instance.client.similarity_search_by_vector.return_value = mock_docs

    # Test search without filters
    vectors = [[0.1, 0.2, 0.3]]
    results = langchain_instance.search(query="", vectors=vectors, limit=2)

    langchain_instance.client.similarity_search_by_vector.assert_called_once_with(embedding=vectors, k=2)

    assert len(results) == 2
    assert results[0].id == "id1"
    assert results[0].payload == {"name": "vector1"}
    assert results[1].id == "id2"
    assert results[1].payload == {"name": "vector2"}

    # Test search with filters
    filters = {"name": "vector1"}
    langchain_instance.search(query="", vectors=vectors, limit=2, filters=filters)
    langchain_instance.client.similarity_search_by_vector.assert_called_with(embedding=vectors, k=2, filter=filters)


def test_search_vectors_with_agent_id_run_id_filters(langchain_instance):
    """Test search with agent_id and run_id filters."""
    # Mock search results
    mock_docs = [
        Mock(metadata={"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}, id="id1"),
        Mock(metadata={"user_id": "bob", "agent_id": "agent2", "run_id": "run2"}, id="id2")
    ]
    langchain_instance.client.similarity_search_by_vector.return_value = mock_docs

    vectors = [[0.1, 0.2, 0.3]]
    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = langchain_instance.search(query="", vectors=vectors, limit=2, filters=filters)

    # Verify that filters were passed to the underlying vector store
    langchain_instance.client.similarity_search_by_vector.assert_called_once_with(
        embedding=vectors, k=2, filter=filters
    )

    assert len(results) == 2
    assert results[0].payload["user_id"] == "alice"
    assert results[0].payload["agent_id"] == "agent1"
    assert results[0].payload["run_id"] == "run1"


def test_search_vectors_with_single_filter(langchain_instance):
    """Test search with single filter."""
    # Mock search results
    mock_docs = [Mock(metadata={"user_id": "alice"}, id="id1")]
    langchain_instance.client.similarity_search_by_vector.return_value = mock_docs

    vectors = [[0.1, 0.2, 0.3]]
    filters = {"user_id": "alice"}
    results = langchain_instance.search(query="", vectors=vectors, limit=2, filters=filters)

    # Verify that filters were passed to the underlying vector store
    langchain_instance.client.similarity_search_by_vector.assert_called_once_with(
        embedding=vectors, k=2, filter=filters
    )

    assert len(results) == 1
    assert results[0].payload["user_id"] == "alice"


def test_search_vectors_with_no_filters(langchain_instance):
    """Test search with no filters."""
    # Mock search results
    mock_docs = [Mock(metadata={"name": "vector1"}, id="id1")]
    langchain_instance.client.similarity_search_by_vector.return_value = mock_docs

    vectors = [[0.1, 0.2, 0.3]]
    results = langchain_instance.search(query="", vectors=vectors, limit=2, filters=None)

    # Verify that no filters were passed to the underlying vector store
    langchain_instance.client.similarity_search_by_vector.assert_called_once_with(
        embedding=vectors, k=2
    )

    assert len(results) == 1


def test_get_vector(langchain_instance):
    # Mock get result
    mock_doc = Mock(metadata={"name": "vector1"}, id="id1")
    langchain_instance.client.get_by_ids.return_value = [mock_doc]

    # Test get existing vector
    result = langchain_instance.get("id1")
    langchain_instance.client.get_by_ids.assert_called_once_with(["id1"])

    assert result is not None
    assert result.id == "id1"
    assert result.payload == {"name": "vector1"}

    # Test get non-existent vector
    langchain_instance.client.get_by_ids.return_value = []
    result = langchain_instance.get("non_existent_id")
    assert result is None


def test_list_with_filters(langchain_instance):
    """Test list with agent_id and run_id filters."""
    # Mock the _collection.get method
    mock_collection = Mock()
    mock_collection.get.return_value = {
        "ids": [["id1"]],
        "metadatas": [[{"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}]],
        "documents": [["test document"]]
    }
    langchain_instance.client._collection = mock_collection

    filters = {"user_id": "alice", "agent_id": "agent1", "run_id": "run1"}
    results = langchain_instance.list(filters=filters, limit=10)

    # Verify that the collection.get method was called with the correct filters
    mock_collection.get.assert_called_once_with(where=filters, limit=10)

    # Verify the results
    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].payload["user_id"] == "alice"
    assert results[0][0].payload["agent_id"] == "agent1"
    assert results[0][0].payload["run_id"] == "run1"


def test_list_with_single_filter(langchain_instance):
    """Test list with single filter."""
    # Mock the _collection.get method
    mock_collection = Mock()
    mock_collection.get.return_value = {
        "ids": [["id1"]],
        "metadatas": [[{"user_id": "alice"}]],
        "documents": [["test document"]]
    }
    langchain_instance.client._collection = mock_collection

    filters = {"user_id": "alice"}
    results = langchain_instance.list(filters=filters, limit=10)

    # Verify that the collection.get method was called with the correct filter
    mock_collection.get.assert_called_once_with(where=filters, limit=10)

    # Verify the results
    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].payload["user_id"] == "alice"


def test_list_with_no_filters(langchain_instance):
    """Test list with no filters."""
    # Mock the _collection.get method
    mock_collection = Mock()
    mock_collection.get.return_value = {
        "ids": [["id1"]],
        "metadatas": [[{"name": "vector1"}]],
        "documents": [["test document"]]
    }
    langchain_instance.client._collection = mock_collection

    results = langchain_instance.list(filters=None, limit=10)

    # Verify that the collection.get method was called with no filters
    mock_collection.get.assert_called_once_with(where=None, limit=10)

    # Verify the results
    assert len(results) == 1
    assert len(results[0]) == 1
    assert results[0][0].payload["name"] == "vector1"


def test_list_with_exception(langchain_instance):
    """Test list when an exception occurs."""
    # Mock the _collection.get method to raise an exception
    mock_collection = Mock()
    mock_collection.get.side_effect = Exception("Test exception")
    langchain_instance.client._collection = mock_collection

    results = langchain_instance.list(filters={"user_id": "alice"}, limit=10)

    # Verify that an empty list is returned when an exception occurs
    assert results == []
