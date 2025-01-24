from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.jina import JinaEmbedding


@pytest.fixture
def mock_jina_client(monkeypatch):
    # Clear any existing env var
    monkeypatch.delenv("JINA_API_KEY", raising=False)
    with patch("mem0.embeddings.jina.requests") as mock_req:
        yield mock_req


def test_embed_default_model(mock_jina_client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "default_key")  # Set a default key
    config = BaseEmbedderConfig()
    embedder = JinaEmbedding(config)
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer default_key"  # Use the default key
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Test embedding"}]
        }
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_jina_client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_key")
    config = BaseEmbedderConfig(model="jina-embeddings-v3", embedding_dims=1024)
    embedder = JinaEmbedding(config)
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [0.4, 0.5, 0.6]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test_key"
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Test embedding"}]
        }
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_jina_client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_key")
    config = BaseEmbedderConfig()
    embedder = JinaEmbedding(config)
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [0.7, 0.8, 0.9]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test_key"
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Hello world"}]
        }
    )
    assert result == [0.7, 0.8, 0.9]


def test_embed_with_model_kwargs(mock_jina_client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_key")
    config = BaseEmbedderConfig(model_kwargs={"dimensions": 512, "normalized": True})
    embedder = JinaEmbedding(config)
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [1.0, 1.1, 1.2]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Test with kwargs")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test_key"
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Test with kwargs"}],
            "dimensions": 512,
            "normalized": True
        }
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_without_api_key_env_var(mock_jina_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = JinaEmbedding(config)
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [1.3, 1.4, 1.5]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer test_key"
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Testing API key"}]
        }
    )
    assert result == [1.3, 1.4, 1.5]


def test_embed_uses_environment_api_key(mock_jina_client, monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = JinaEmbedding(config)
    
    mock_response = Mock()
    mock_response.json.return_value = {"data": [{"embedding": [1.6, 1.7, 1.8]}]}
    mock_jina_client.post.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_jina_client.post.assert_called_once_with(
        "https://api.jina.ai/v1/embeddings",
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer env_key"
        },
        json={
            "model": "jina-embeddings-v3",
            "input": [{"text": "Environment key test"}]
        }
    )
    assert result == [1.6, 1.7, 1.8]


def test_raises_error_without_api_key():
    config = BaseEmbedderConfig()
    with pytest.raises(ValueError, match="Jina API key is required"):
        JinaEmbedding(config) 