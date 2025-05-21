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
