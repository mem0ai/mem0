from unittest.mock import Mock, patch

import numpy as np
import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig

try:
    from mem0.embeddings.fastembed import FastEmbedEmbedding
except ImportError:
    pytest.skip("fastembed not installed", allow_module_level=True)
  

@pytest.fixture
def mock_fastembed_client():
    with patch("mem0.embeddings.fastembed.TextEmbedding") as mock_fastembed:
        mock_client = Mock()
        mock_fastembed.return_value = mock_client
        yield mock_client


def test_embed_with_jina_model(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)
    
    mock_embedding = np.array([0.1, 0.2, 0.3, 0.4, 0.5])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])
    
    text = "Sample text to embed."
    embedding = embedder.embed(text)
    
    mock_fastembed_client.embed.assert_called_once_with(text)
    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_embed_removes_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_embedding = np.array([0.7, 0.8, 0.9])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])

    text_with_newlines = "Hello\nworld"
    embedding = embedder.embed(text_with_newlines)

    mock_fastembed_client.embed.assert_called_once_with("Hello world")
    assert embedding == [0.7, 0.8, 0.9]


def test_embed_batch(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter([np.array([0.1, 0.2]), np.array([0.3, 0.4])])

    texts = ["first text", "second text"]
    result = embedder.embed_batch(texts)

    mock_fastembed_client.embed.assert_called_once_with(["first text", "second text"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_single_call(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter([np.array([0.1] * 768)] * 50)
    embedder.embed_batch([f"text {i}" for i in range(50)])

    assert mock_fastembed_client.embed.call_count == 1


def test_embed_batch_strips_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter([np.array([0.5, 0.6])])
    embedder.embed_batch(["hello\nworld"])

    mock_fastembed_client.embed.assert_called_once_with(["hello world"])