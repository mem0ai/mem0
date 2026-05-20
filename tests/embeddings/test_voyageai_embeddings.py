from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.voyageai import VoyageAIEmbedding


@pytest.fixture
def mock_voyageai_client():
    with patch("mem0.embeddings.voyageai.voyageai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_voyageai_client):
    config = BaseEmbedderConfig()
    embedder = VoyageAIEmbedding(config)
    mock_response = MagicMock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_voyageai_client.embed.assert_called_once_with(["Hello world"], model="voyage-3", input_type=None)
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_voyageai_client):
    config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=2048)
    embedder = VoyageAIEmbedding(config)
    mock_response = MagicMock()
    mock_response.embeddings = [[0.4, 0.5, 0.6]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_voyageai_client.embed.assert_called_once_with(["Test embedding"], model="voyage-3-large", input_type=None, output_dimension=2048)
    assert result == [0.4, 0.5, 0.6]


def test_embed_with_memory_action(mock_voyageai_client):
    expected_input_types = {
        "add": "document",
        "update": "document",
        "search": "query",
    }
    for action, input_type in expected_input_types.items():
        config = BaseEmbedderConfig()
        embedder = VoyageAIEmbedding(config)
        mock_response = MagicMock()
        mock_response.embeddings = [[0.1, 0.2, 0.3]]
        mock_voyageai_client.embed.return_value = mock_response

        result = embedder.embed("Hello world", memory_action=action)

        mock_voyageai_client.embed.assert_called_with(["Hello world"], model="voyage-3", input_type=input_type)
        assert result == [0.1, 0.2, 0.3]


def test_embed_without_api_key_env_var(mock_voyageai_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = VoyageAIEmbedding(config)
    mock_response = MagicMock()
    mock_response.embeddings = [[1.0, 1.1, 1.2]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_voyageai_client.embed.assert_called_once_with(["Testing API key"], model="voyage-3", input_type=None)
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_voyageai_client, monkeypatch):
    monkeypatch.setenv("VOYAGEAI_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = VoyageAIEmbedding(config)
    mock_response = MagicMock()
    mock_response.embeddings = [[1.3, 1.4, 1.5]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_voyageai_client.embed.assert_called_once_with(["Environment key test"], model="voyage-3", input_type=None)
    assert result == [1.3, 1.4, 1.5]


def test_embed_batch(mock_voyageai_client):
    config = BaseEmbedderConfig()
    embedder = VoyageAIEmbedding(config)
    mock_response = MagicMock()
    mock_response.embeddings = [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed_batch(["Hello world", "Goodbye world"])

    mock_voyageai_client.embed.assert_called_once_with(["Hello world", "Goodbye world"], model="voyage-3", input_type="document")
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]
