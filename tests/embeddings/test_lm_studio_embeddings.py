from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.lmstudio import LMStudioEmbedding


@pytest.fixture
def mock_lm_studio_client():
    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_client.embeddings.create.return_value = Mock(data=[Mock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5])])
        mock_openai.return_value = mock_client
        yield mock_client


def test_embed_text(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_lm_studio_client.embeddings.create.assert_called_once_with(
        input=["Sample text to embed."], model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
    )

    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_embed_batch_single_call(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    mock_item0 = Mock(index=0, embedding=[0.1, 0.2, 0.3])
    mock_item1 = Mock(index=1, embedding=[0.4, 0.5, 0.6])
    mock_lm_studio_client.embeddings.create.return_value = Mock(data=[mock_item0, mock_item1])

    texts = ["First text.", "Second text."]
    embeddings = embedder.embed_batch(texts)

    mock_lm_studio_client.embeddings.create.assert_called_once_with(
        input=texts, model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
    )
    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_empty_list(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_lm_studio_client.embeddings.create.assert_not_called()


def test_embed_batch_strips_newlines(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    mock_item0 = Mock(index=0, embedding=[0.1, 0.2, 0.3])
    mock_lm_studio_client.embeddings.create.return_value = Mock(data=[mock_item0])

    embedder.embed_batch(["line one\nline two"])

    mock_lm_studio_client.embeddings.create.assert_called_once_with(
        input=["line one line two"], model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
    )


def test_embed_batch_count_mismatch_raises(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    mock_item0 = Mock(index=0, embedding=[0.1, 0.2, 0.3])
    mock_lm_studio_client.embeddings.create.return_value = Mock(data=[mock_item0])

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_base_url_honors_lmstudio_base_url_env(mock_lm_studio_client, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lmstudio.internal:9000/v1")

    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        LMStudioEmbedding(BaseEmbedderConfig())

    assert mock_openai.call_args.kwargs["base_url"] == "http://lmstudio.internal:9000/v1"


def test_base_url_prefers_explicit_config_over_env(mock_lm_studio_client, monkeypatch):
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "http://lmstudio.internal:9000/v1")

    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        LMStudioEmbedding(BaseEmbedderConfig(lmstudio_base_url="http://explicit:1234/v1"))

    assert mock_openai.call_args.kwargs["base_url"] == "http://explicit:1234/v1"


def test_base_url_falls_back_to_localhost_default(mock_lm_studio_client, monkeypatch):
    monkeypatch.delenv("LMSTUDIO_BASE_URL", raising=False)

    with patch("mem0.embeddings.lmstudio.OpenAI") as mock_openai:
        embedder = LMStudioEmbedding(BaseEmbedderConfig())

    assert mock_openai.call_args.kwargs["base_url"] == "http://localhost:1234/v1"
    assert embedder.config.lmstudio_base_url == "http://localhost:1234/v1"
