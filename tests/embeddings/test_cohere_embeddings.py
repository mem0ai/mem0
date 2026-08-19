from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.cohere import CohereEmbedding


@pytest.fixture
def mock_cohere_client():
    with patch("mem0.embeddings.cohere.cohere.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_cohere_client):
    config = BaseEmbedderConfig()
    embedder = CohereEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_cohere_client.embed.return_value = mock_response

    result = embedder.embed("Hello world", memory_action="add")

    mock_cohere_client.embed.assert_called_once_with(
        texts=["Hello world"],
        model="embed-english-v3.0",
        input_type="search_document"
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_cohere_client):
    config = BaseEmbedderConfig(model="embed-multilingual-v3.0")
    embedder = CohereEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.4, 0.5, 0.6]]
    mock_cohere_client.embed.return_value = mock_response

    result = embedder.embed("Test embedding", memory_action="search")

    mock_cohere_client.embed.assert_called_once_with(
        texts=["Test embedding"],
        model="embed-multilingual-v3.0",
        input_type="search_query"
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_cohere_client):
    config = BaseEmbedderConfig()
    embedder = CohereEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.7, 0.8, 0.9]]
    mock_cohere_client.embed.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_cohere_client.embed.assert_called_once_with(
        texts=["Hello world"],
        model="embed-english-v3.0",
        input_type="search_document"
    )
    assert result == [0.7, 0.8, 0.9]


def test_embed_without_api_key_env_var(mock_cohere_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = CohereEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[1.0, 1.1, 1.2]]
    mock_cohere_client.embed.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_cohere_client.embed.assert_called_once_with(
        texts=["Testing API key"],
        model="embed-english-v3.0",
        input_type="search_document"
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_batch_returns_all_embeddings(mock_cohere_client):
    config = BaseEmbedderConfig()
    embedder = CohereEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2], [0.3, 0.4]]
    mock_cohere_client.embed.return_value = mock_response

    result = embedder.embed_batch(["first text", "second text"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_count_mismatch_raises(mock_cohere_client):
    config = BaseEmbedderConfig()
    embedder = CohereEmbedding(config)
    # Provider returns fewer embeddings than inputs (partial/dropped batch).
    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2]]
    mock_cohere_client.embed.return_value = mock_response

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])
