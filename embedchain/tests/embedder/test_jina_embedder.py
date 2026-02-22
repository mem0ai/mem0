from unittest.mock import MagicMock, patch

import pytest

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.jina import JinaEmbedder
from embedchain.models import VectorDimensions


def test_jina_embedder_with_default_model(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_api_key")
    config = BaseEmbedderConfig()
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        assert embedder.config.model == "jina-embeddings-v5-text-nano"
        assert embedder.vector_dimension == VectorDimensions.JINA_NANO.value
        mock_embedding_fn.assert_called_once_with(
            api_key="test_api_key",
            model_name="jina-embeddings-v5-text-nano",
            task="retrieval.passage",
            use_local=False,
            model_kwargs={},
        )


def test_jina_embedder_with_custom_model(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_api_key")
    config = BaseEmbedderConfig(model="jina-embeddings-v5-text-small")
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        assert embedder.config.model == "jina-embeddings-v5-text-small"
        assert embedder.vector_dimension == VectorDimensions.JINA_SMALL.value
        mock_embedding_fn.assert_called_once_with(
            api_key="test_api_key",
            model_name="jina-embeddings-v5-text-small",
            task="retrieval.passage",
            use_local=False,
            model_kwargs={},
        )


def test_jina_embedder_with_custom_task(monkeypatch):
    monkeypatch.setenv("JINA_API_KEY", "test_api_key")
    config = BaseEmbedderConfig(
        model="jina-embeddings-v5-text-nano",
        model_kwargs={"task": "retrieval.query"}
    )
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        mock_embedding_fn.assert_called_once_with(
            api_key="test_api_key",
            model_name="jina-embeddings-v5-text-nano",
            task="retrieval.query",
            use_local=False,
            model_kwargs={"task": "retrieval.query"},
        )


def test_jina_embedder_without_api_key():
    config = BaseEmbedderConfig()
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction'):
        with pytest.raises(ValueError, match="JINA_API_KEY"):
            JinaEmbedder(config=config)


def test_jina_embedder_local_mode_nano():
    config = BaseEmbedderConfig(
        model="jinaai/jina-embeddings-v5-text-nano",
        model_kwargs={"use_local": True}
    )
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        assert embedder.config.model == "jinaai/jina-embeddings-v5-text-nano"
        assert embedder.vector_dimension == VectorDimensions.JINA_NANO.value
        mock_embedding_fn.assert_called_once_with(
            api_key=None,
            model_name="jinaai/jina-embeddings-v5-text-nano",
            task="retrieval.passage",
            use_local=True,
            model_kwargs={"use_local": True},
        )


def test_jina_embedder_local_mode_small():
    config = BaseEmbedderConfig(
        model="jinaai/jina-embeddings-v5-text-small",
        model_kwargs={"use_local": True}
    )
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        assert embedder.config.model == "jinaai/jina-embeddings-v5-text-small"
        assert embedder.vector_dimension == VectorDimensions.JINA_SMALL.value
        mock_embedding_fn.assert_called_once_with(
            api_key=None,
            model_name="jinaai/jina-embeddings-v5-text-small",
            task="retrieval.passage",
            use_local=True,
            model_kwargs={"use_local": True},
        )


def test_jina_embedder_local_mode_short_name():
    """Test local mode with short model name (auto-converted to HF format)"""
    config = BaseEmbedderConfig(
        model="jina-embeddings-v5-text-nano",
        model_kwargs={"use_local": True}
    )
    
    with patch('embedchain.embedder.jina.JinaEmbeddingFunction') as mock_embedding_fn:
        embedder = JinaEmbedder(config=config)
        assert embedder.config.model == "jina-embeddings-v5-text-nano"
        assert embedder.vector_dimension == VectorDimensions.JINA_NANO.value
        mock_embedding_fn.assert_called_once_with(
            api_key=None,
            model_name="jina-embeddings-v5-text-nano",
            task="retrieval.passage",
            use_local=True,
            model_kwargs={"use_local": True},
        )
