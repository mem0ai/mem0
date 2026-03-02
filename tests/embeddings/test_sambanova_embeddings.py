from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.sambanova import SambaNovaEmbedding


@pytest.fixture
def mock_sambanova_client():
    with patch("mem0.embeddings.sambanova.SambaNova") as mock_sambanova:
        mock_client = Mock()
        mock_sambanova.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_sambanova_client):
    config = BaseEmbedderConfig()
    embedder = SambaNovaEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_sambanova_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_sambanova_client.embeddings.create.assert_called_once_with(
        input="Hello world", model="E5-Mistral-7B-Instruct"
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_without_api_key_env_var(mock_sambanova_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = SambaNovaEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.0, 1.1, 1.2])]
    mock_sambanova_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_sambanova_client.embeddings.create.assert_called_once_with(
        input="Testing API key", model="E5-Mistral-7B-Instruct"
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_sambanova_client, monkeypatch):
    monkeypatch.setenv("SAMBANOVA_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = SambaNovaEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_sambanova_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_sambanova_client.embeddings.create.assert_called_once_with(
        input="Environment key test", model="E5-Mistral-7B-Instruct"
    )
    assert result == [1.3, 1.4, 1.5]
