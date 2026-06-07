from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.ollama import OllamaEmbedding


@pytest.fixture
def mock_ollama_client():
    with patch("mem0.embeddings.ollama.Client") as mock_ollama:
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "nomic-embed-text"}]}
        mock_ollama.return_value = mock_client
        yield mock_client


def test_embed_text(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_response = {"embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]]}
    mock_ollama_client.embed.return_value = mock_response

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_ollama_client.embed.assert_called_once_with(model="nomic-embed-text", input=text)

    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_ensure_model_exists(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_ollama_client.pull.assert_not_called()

    mock_ollama_client.list.return_value = {"models": []}

    embedder._ensure_model_exists()

    mock_ollama_client.pull.assert_called_once_with("nomic-embed-text")


def test_ensure_model_exists_normalizes_latest_tag(mock_ollama_client):
    """Model 'nomic-embed-text' should match 'nomic-embed-text:latest' from ollama list."""
    mock_ollama_client.list.return_value = {"models": [{"name": "nomic-embed-text:latest"}]}
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    OllamaEmbedding(config)

    mock_ollama_client.pull.assert_not_called()


def test_embed_empty_response_raises(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_ollama_client.embed.return_value = {"embeddings": []}

    with pytest.raises(ValueError, match="returned no embeddings"):
        embedder.embed("some text")


def test_embed_batch(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_response = {"embeddings": [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]}
    mock_ollama_client.embed.return_value = mock_response

    texts = ["First text.", "Second text."]
    embeddings = embedder.embed_batch(texts)

    mock_ollama_client.embed.assert_called_once_with(model="nomic-embed-text", input=texts)
    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_strips_newlines(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_response = {"embeddings": [[0.1, 0.2, 0.3]]}
    mock_ollama_client.embed.return_value = mock_response

    embedder.embed_batch(["line1\nline2"])

    mock_ollama_client.embed.assert_called_once_with(model="nomic-embed-text", input=["line1 line2"])


def test_embed_batch_empty_response_raises(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_ollama_client.embed.return_value = {"embeddings": []}

    with pytest.raises(ValueError, match="returned no embeddings"):
        embedder.embed_batch(["some text"])
