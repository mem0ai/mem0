import sys
from unittest.mock import Mock, patch

import pytest

from mem0.configs.rerankers.voyageai import VoyageAIRerankerConfig


@pytest.fixture
def mock_voyageai_client():
    """Mock the voyageai module before VoyageAIReranker imports it."""
    mock_voyageai = Mock()
    mock_client = Mock()
    mock_voyageai.Client.return_value = mock_client

    with patch.dict(sys.modules, {"voyageai": mock_voyageai}):
        from mem0.reranker.voyageai_reranker import VoyageAIReranker

        yield mock_client, VoyageAIReranker


def test_rerank_default_model(mock_voyageai_client):
    """Test reranking with default model."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    # Mock rerank response
    mock_result1 = Mock()
    mock_result1.index = 1
    mock_result1.relevance_score = 0.9
    mock_result2 = Mock()
    mock_result2.index = 0
    mock_result2.relevance_score = 0.7
    mock_response = Mock()
    mock_response.results = [mock_result1, mock_result2]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Document 1"}, {"memory": "Document 2"}]
    result = reranker.rerank("test query", documents)

    mock_client.rerank.assert_called_once_with(
        query="test query",
        documents=["Document 1", "Document 2"],
        model="rerank-2",
        top_k=2,
        truncation=True,
    )
    assert len(result) == 2
    assert result[0]["rerank_score"] == 0.9
    assert result[1]["rerank_score"] == 0.7


def test_rerank_custom_model(mock_voyageai_client):
    """Test reranking with custom model."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key", model="rerank-2-lite")
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.8
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Document"}]
    reranker.rerank("query", documents)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["model"] == "rerank-2-lite"


def test_rerank_with_top_k(mock_voyageai_client):
    """Test reranking with top_k parameter."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.9
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Doc 1"}, {"memory": "Doc 2"}, {"memory": "Doc 3"}]
    reranker.rerank("query", documents, top_k=1)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["top_k"] == 1


def test_rerank_with_config_top_k(mock_voyageai_client):
    """Test reranking uses config top_k when not passed as argument."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key", top_k=5)
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.9
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Doc"}]
    reranker.rerank("query", documents)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["top_k"] == 5


def test_rerank_truncation_disabled(mock_voyageai_client):
    """Test reranking with truncation disabled."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key", truncation=False)
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.8
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Document"}]
    reranker.rerank("query", documents)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["truncation"] is False


def test_rerank_empty_documents(mock_voyageai_client):
    """Test reranking with empty document list returns empty."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    result = reranker.rerank("query", [])

    assert result == []
    mock_client.rerank.assert_not_called()


def test_rerank_extracts_text_field(mock_voyageai_client):
    """Test reranking extracts 'text' field from documents."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.8
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"text": "Text content"}]
    reranker.rerank("query", documents)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["documents"] == ["Text content"]


def test_rerank_extracts_content_field(mock_voyageai_client):
    """Test reranking extracts 'content' field from documents."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.8
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"content": "Content field"}]
    reranker.rerank("query", documents)

    call_kwargs = mock_client.rerank.call_args[1]
    assert call_kwargs["documents"] == ["Content field"]


def test_rerank_uses_environment_api_key(mock_voyageai_client, monkeypatch):
    """Test API key is read from environment variable."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    monkeypatch.setenv("VOYAGE_API_KEY", "env_key")
    config = VoyageAIRerankerConfig()

    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.8
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Doc"}]
    result = reranker.rerank("query", documents)
    assert len(result) == 1


def test_missing_api_key_raises_error(mock_voyageai_client, monkeypatch):
    """Test that missing API key raises ValueError."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    config = VoyageAIRerankerConfig()

    with pytest.raises(ValueError, match="VoyageAI API key is required"):
        VoyageAIReranker(config)


def test_rerank_preserves_original_document_fields(mock_voyageai_client):
    """Test reranking preserves all original document fields."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    mock_result = Mock()
    mock_result.index = 0
    mock_result.relevance_score = 0.85
    mock_response = Mock()
    mock_response.results = [mock_result]
    mock_client.rerank.return_value = mock_response

    documents = [{"memory": "Doc", "id": "123", "metadata": {"source": "test"}}]
    result = reranker.rerank("query", documents)

    assert result[0]["memory"] == "Doc"
    assert result[0]["id"] == "123"
    assert result[0]["metadata"] == {"source": "test"}
    assert result[0]["rerank_score"] == 0.85


def test_rerank_fallback_on_error(mock_voyageai_client):
    """Test reranking falls back to original order on API error."""
    mock_client, VoyageAIReranker = mock_voyageai_client
    config = VoyageAIRerankerConfig(api_key="test_key")
    reranker = VoyageAIReranker(config)

    mock_client.rerank.side_effect = Exception("API error")

    documents = [{"memory": "Doc 1"}, {"memory": "Doc 2"}]
    result = reranker.rerank("query", documents, top_k=1)

    # Should return original docs with 0.0 scores
    assert len(result) == 1
    assert result[0]["rerank_score"] == 0.0
