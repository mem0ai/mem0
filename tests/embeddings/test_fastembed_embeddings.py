import json
from unittest.mock import Mock, patch

import pytest
import numpy as np
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
    assert isinstance(embedding, list)
    json.dumps(embedding)


def test_embed_removes_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)
    
    mock_embedding = np.array([0.7, 0.8, 0.9])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])
    
    text_with_newlines = "Hello\nworld"
    embedding = embedder.embed(text_with_newlines)
    
    mock_fastembed_client.embed.assert_called_once_with("Hello world")
    assert embedding == [0.7, 0.8, 0.9]


def test_embed_normalizes_iterable_without_tolist(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=3)
    embedder = FastEmbedEmbedding(config)
    mock_fastembed_client.embed.return_value = iter([(0.1, 0.2, 0.3)])

    embedding = embedder.embed("Sample text")

    assert embedding == [0.1, 0.2, 0.3]
    assert isinstance(embedding, list)
