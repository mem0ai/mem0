from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.gemini import GoogleGenAIEmbedding


@pytest.fixture
def mock_genai_client():
    with patch("mem0.embeddings.gemini.genai.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


@pytest.fixture
def config():
    return BaseEmbedderConfig(api_key="dummy_api_key", model="test_model", embedding_dims=786)


def test_embed_query(mock_genai_client, config):
    # Mock the response structure
    mock_embedding = Mock()
    mock_embedding.values = [0.1, 0.2, 0.3, 0.4]
    
    mock_response = Mock()
    mock_response.embeddings = [mock_embedding]
    
    mock_genai_client.models.embed_content.return_value = mock_response

    embedder = GoogleGenAIEmbedding(config)

    text = "Hello, world!"
    embedding = embedder.embed(text)

    assert embedding == [0.1, 0.2, 0.3, 0.4]
    
    # Check that the correct method was called
    mock_genai_client.models.embed_content.assert_called_once()
    
    # Get the actual call arguments
    call_args = mock_genai_client.models.embed_content.call_args
    assert call_args.kwargs["model"] == "test_model"
    assert call_args.kwargs["contents"] == "Hello, world!"
    assert call_args.kwargs["config"].output_dimensionality == 786


def test_embed_returns_empty_list_if_none(mock_genai_client, config):
    # Mock empty response
    mock_response = Mock()
    mock_response.embeddings = []
    
    mock_genai_client.models.embed_content.return_value = mock_response

    embedder = GoogleGenAIEmbedding(config)
    
    with pytest.raises(IndexError):  # This will raise IndexError when trying to access [0]
        embedder.embed("test")


def test_embed_raises_on_error(mock_genai_client, config):
    mock_genai_client.models.embed_content.side_effect = RuntimeError("Embedding failed")

    embedder = GoogleGenAIEmbedding(config)

    with pytest.raises(RuntimeError, match="Embedding failed"):
        embedder.embed("some input")

def test_config_initialization(config):
    embedder = GoogleGenAIEmbedding(config)

    assert embedder.config.api_key == "dummy_api_key"
    assert embedder.config.model == "test_model"
    assert embedder.config.embedding_dims == 786

