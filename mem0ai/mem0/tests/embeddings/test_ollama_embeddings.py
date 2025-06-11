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

    mock_response = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
    mock_ollama_client.embeddings.return_value = mock_response

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_ollama_client.embeddings.assert_called_once_with(model="nomic-embed-text", prompt=text)

    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_ensure_model_exists(mock_ollama_client):
    config = BaseEmbedderConfig(model="nomic-embed-text", embedding_dims=512)
    embedder = OllamaEmbedding(config)

    mock_ollama_client.pull.assert_not_called()

    mock_ollama_client.list.return_value = {"models": []}

    embedder._ensure_model_exists()

    mock_ollama_client.pull.assert_called_once_with("nomic-embed-text")
