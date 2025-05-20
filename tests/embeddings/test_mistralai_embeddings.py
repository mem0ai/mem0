from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.mistralai import MistralAIEmbedding


@pytest.fixture
def mock_mistralai_client():
    with patch("mem0.embeddings.mistralai.Mistral") as mock_mistralai:
        mock_client = Mock()
        mock_mistralai.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_mistralai_client):
    config = BaseEmbedderConfig()
    embedder = MistralAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_mistralai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_mistralai_client.embeddings.create.assert_called_once_with(input=["Hello world"], model="mistral-embed")
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_mistralai_client):
    config = BaseEmbedderConfig(model="mistral-embed")
    embedder = MistralAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_mistralai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_mistralai_client.embeddings.create.assert_called_once_with(input=["Test embedding"], model="mistral-embed")
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_mistralai_client):
    config = BaseEmbedderConfig()
    embedder = MistralAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.7, 0.8, 0.9])]
    mock_mistralai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_mistralai_client.embeddings.create.assert_called_once_with(input=["Hello world"], model="mistral-embed")
    assert result == [0.7, 0.8, 0.9]


def test_embed_without_api_key_env_var(mock_mistralai_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = MistralAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.0, 1.1, 1.2])]
    mock_mistralai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_mistralai_client.embeddings.create.assert_called_once_with(input=["Testing API key"], model="mistral-embed")
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_mistralai_client, monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = MistralAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_mistralai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_mistralai_client.embeddings.create.assert_called_once_with(
        input=["Environment key test"], model="mistral-embed"
    )
    assert result == [1.3, 1.4, 1.5]
