from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.openai import OpenAIEmbedding


@pytest.fixture
def mock_openai_client():
    with patch("mem0.embeddings.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-2-medium", embedding_dims=1024)
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Test embedding"], model="text-embedding-2-medium", dimensions=1024
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.7, 0.8, 0.9])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [0.7, 0.8, 0.9]


def test_embed_without_api_key_env_var(mock_openai_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.0, 1.1, 1.2])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Testing API key"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_openai_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Environment key test"], model="text-embedding-3-small", dimensions=1536
    )
    assert result == [1.3, 1.4, 1.5]
