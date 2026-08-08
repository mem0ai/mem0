from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.openai import OpenAIEmbedding


@pytest.fixture
def mock_openai_client():
    with patch("mem0.embeddings.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello world")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", encoding_format="float"
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-2-medium", embedding_dims=1024)
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Test embedding")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Test embedding"], model="text-embedding-2-medium", dimensions=1024, encoding_format="float"
    )
    assert result == [0.4, 0.5, 0.6]


def test_embed_removes_newlines(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.7, 0.8, 0.9])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Hello\nworld")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello world"], model="text-embedding-3-small", encoding_format="float"
    )
    assert result == [0.7, 0.8, 0.9]


def test_embed_without_api_key_env_var(mock_openai_client):
    config = BaseEmbedderConfig(api_key="test_key")
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.0, 1.1, 1.2])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Testing API key")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Testing API key"], model="text-embedding-3-small", encoding_format="float"
    )
    assert result == [1.0, 1.1, 1.2]


def test_embed_uses_environment_api_key(mock_openai_client, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env_key")
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Environment key test"], model="text-embedding-3-small", encoding_format="float"
    )
    assert result == [1.3, 1.4, 1.5]


def test_embed_passes_encoding_format_float(mock_openai_client):
    """Verify encoding_format='float' is always passed to prevent base64 issues with proxies.

    The OpenAI SDK defaults to encoding_format='base64' when not specified,
    which breaks OpenAI-compatible proxies (OpenRouter, LiteLLM, vLLM, etc.)
    that don't support base64 decoding. See #4057.
    """
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_response

    embedder.embed("Proxy compatibility test")

    call_kwargs = mock_openai_client.embeddings.create.call_args
    assert call_kwargs.kwargs.get("encoding_format") == "float" or call_kwargs[1].get("encoding_format") == "float"


def test_embed_passes_dimensions_only_when_explicit(mock_openai_client):
    """Matryoshka / truncated embeddings: dimensions sent only if user sets embedding_dims (#4153)."""
    config = BaseEmbedderConfig(embedding_dims=256)
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1] * 256)]
    mock_openai_client.embeddings.create.return_value = mock_response

    embedder.embed("truncate me")

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["truncate me"], model="text-embedding-3-small", dimensions=256, encoding_format="float"
    )


def test_embed_batch_returns_all_embeddings(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    mock_response = Mock()
    mock_response.data = [
        Mock(index=0, embedding=[0.1, 0.2]),
        Mock(index=1, embedding=[0.3, 0.4]),
    ]
    mock_openai_client.embeddings.create.return_value = mock_response

    result = embedder.embed_batch(["first text", "second text"])

    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_count_mismatch_raises(mock_openai_client):
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)
    # Provider returns fewer embeddings than inputs (partial/dropped batch).
    mock_response = Mock()
    mock_response.data = [Mock(index=0, embedding=[0.1, 0.2])]
    mock_openai_client.embeddings.create.return_value = mock_response

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_embed_batch_respects_configured_batch_size(mock_openai_client):
    # DashScope text-embedding-v4 and similar OpenAI-compatible providers cap a
    # request at 10 texts. With embedding_batch_size set, 11 texts must go out
    # as two requests (10 + 1) instead of one oversized request that 400s.
    config = BaseEmbedderConfig(embedding_batch_size=10)
    embedder = OpenAIEmbedding(config)

    def fake_create(**kwargs):
        response = Mock()
        response.data = [Mock(index=i, embedding=[float(i)]) for i in range(len(kwargs["input"]))]
        return response

    mock_openai_client.embeddings.create.side_effect = fake_create

    result = embedder.embed_batch([f"text {i}" for i in range(11)])

    assert mock_openai_client.embeddings.create.call_count == 2
    call_args = mock_openai_client.embeddings.create.call_args_list
    assert len(call_args[0].kwargs["input"]) == 10
    assert len(call_args[1].kwargs["input"]) == 1
    assert len(result) == 11


def test_embed_batch_defaults_to_100(mock_openai_client):
    # Without an override, the batch size stays at OpenAI's limit of 100, so
    # 150 texts go out as two requests (100 + 50).
    config = BaseEmbedderConfig()
    embedder = OpenAIEmbedding(config)

    def fake_create(**kwargs):
        response = Mock()
        response.data = [Mock(index=i, embedding=[float(i)]) for i in range(len(kwargs["input"]))]
        return response

    mock_openai_client.embeddings.create.side_effect = fake_create

    result = embedder.embed_batch([f"text {i}" for i in range(150)])

    assert mock_openai_client.embeddings.create.call_count == 2
    call_args = mock_openai_client.embeddings.create.call_args_list
    assert len(call_args[0].kwargs["input"]) == 100
    assert len(call_args[1].kwargs["input"]) == 50
    assert len(result) == 150
