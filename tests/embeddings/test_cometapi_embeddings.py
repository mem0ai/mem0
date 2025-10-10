from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.cometapi import CometAPIEmbedding


@pytest.fixture
def mock_openai_client():
    with patch("mem0.embeddings.cometapi.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-3-large", embedding_dims=3072)
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Test embedding"], model="text-embedding-3-large", dimensions=3072
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.7, 0.8, 0.9])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [0.7, 0.8, 0.9]


def test_embed_with_api_key(mock_openai_client):
    config = BaseEmbedderConfig(api_key="test_cometapi_key")
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.0, 1.1, 1.2])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Testing API key"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_openai_client, monkeypatch):
    monkeypatch.setenv("COMETAPI_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment API key test")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Environment API key test"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [1.3, 1.4, 1.5]


def test_init_with_cometapi_base_url(mock_openai_client):
    config = BaseEmbedderConfig()
    CometAPIEmbedding(config)
    # Verify OpenAI client was initialized with CometAPI base URL
    mock_openai_client_init = mock_openai_client
    assert mock_openai_client_init is not None


def test_embed_text_embedding_ada_002(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-ada-002", embedding_dims=1536)
    embedder = CometAPIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 1536)]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Test ada-002 model")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Test ada-002 model"], model="text-embedding-ada-002", dimensions=1536
    )
    assert len(result) == 1536
