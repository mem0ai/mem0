"""Tests for FastEmbed embedding provider, including embed_batch."""

import logging
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
    assert list(embedding) == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_embed_removes_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_embedding = np.array([0.7, 0.8, 0.9])
    mock_fastembed_client.embed.return_value = iter([mock_embedding])

    text_with_newlines = "Hello\nworld"
    embedding = embedder.embed(text_with_newlines)

    mock_fastembed_client.embed.assert_called_once_with("Hello world")
    assert list(embedding) == [0.7, 0.8, 0.9]


def test_embed_returns_list_not_ndarray(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter([np.array([0.1, 0.2, 0.3])])

    embedding = embedder.embed("hello")

    assert isinstance(embedding, list)
    assert embedding == [0.1, 0.2, 0.3]


def test_embed_batch_uses_native_list_input(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter(
        [np.array([0.1, 0.2, 0.3]), np.array([0.4, 0.5, 0.6])]
    )
    result = embedder.embed_batch(["hello", "world"])

    mock_fastembed_client.embed.assert_called_once_with(["hello", "world"])
    assert isinstance(result, list)
    assert all(isinstance(r, list) for r in result)
    assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_empty_returns_empty(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_fastembed_client.embed.assert_not_called()


def test_embed_batch_replaces_newlines(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    mock_fastembed_client.embed.return_value = iter([np.array([0.1, 0.2])])
    embedder.embed_batch(["hello\nworld"])

    mock_fastembed_client.embed.assert_called_once_with(["hello world"])


def test_embed_batch_falls_back_on_error(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # First call (from embed_batch) raises, subsequent calls (from fallback embed()) succeed
    mock_fastembed_client.embed.side_effect = [
        RuntimeError("batch failure"),
        iter([np.array([0.1, 0.2])]),
        iter([np.array([0.3, 0.4])]),
    ]
    result = embedder.embed_batch(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_falls_back_on_count_mismatch(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Batch call returns 1 embedding for 2 texts -> count mismatch -> fallback
    mock_fastembed_client.embed.side_effect = [
        iter([np.array([0.1, 0.2])]),  # batch call returns wrong count
        iter([np.array([0.1, 0.2])]),  # fallback embed("a")
        iter([np.array([0.3, 0.4])]),  # fallback embed("b")
    ]
    result = embedder.embed_batch(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_falls_back_on_count_mismatch_extra(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Batch call returns 3 embeddings for 2 texts -> count mismatch -> fallback
    mock_fastembed_client.embed.side_effect = [
        iter([np.array([0.1, 0.2]), np.array([0.3, 0.4]), np.array([0.5, 0.6])]),
        iter([np.array([0.1, 0.2])]),  # fallback embed("a")
        iter([np.array([0.3, 0.4])]),  # fallback embed("b")
    ]
    result = embedder.embed_batch(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_fallback_logs_warning_with_context(mock_fastembed_client, caplog):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Batch call returns 1 embedding for 2 texts -> count mismatch -> fallback
    mock_fastembed_client.embed.side_effect = [
        iter([np.array([0.1, 0.2])]),  # batch call returns wrong count
        iter([np.array([0.1, 0.2])]),  # fallback embed("a")
        iter([np.array([0.3, 0.4])]),  # fallback embed("b")
    ]
    with caplog.at_level(logging.WARNING, logger="mem0.embeddings.fastembed"):
        result = embedder.embed_batch(["a", "b"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    # The fallback warning must carry the exception context: both counts and the model name
    assert any(
        "falling back to per-text embedding" in record.getMessage()
        and "1 embeddings" in record.getMessage()
        and "2 texts" in record.getMessage()
        and "jinaai/jina-embeddings-v2-base-en" in record.getMessage()
        for record in caplog.records
    )


def test_embed_batch_fallback_failure_propagates(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Batch call fails, then the per-text fallback embed() also fails -> error propagates
    mock_fastembed_client.embed.side_effect = [
        RuntimeError("batch failure"),
        RuntimeError("single failure"),
    ]
    with pytest.raises(RuntimeError, match="single failure"):
        embedder.embed_batch(["a", "b"])


def test_embed_batch_passes_memory_action_to_fallback(mock_fastembed_client):
    config = BaseEmbedderConfig(model="jinaai/jina-embeddings-v2-base-en", embedding_dims=768)
    embedder = FastEmbedEmbedding(config)

    # Force the native batch path to fail so the fallback path runs
    mock_fastembed_client.embed.side_effect = RuntimeError("batch failure")

    with patch.object(embedder, "embed", side_effect=[[0.1, 0.2], [0.3, 0.4]]) as embed_spy:
        result = embedder.embed_batch(["a", "b"], memory_action="search")

    assert result == [[0.1, 0.2], [0.3, 0.4]]
    assert embed_spy.call_count == 2
    embed_spy.assert_any_call("a", "search")
    embed_spy.assert_any_call("b", "search")
