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


def test_embed_batch(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    def make_item(idx, emb):
        item = Mock()
        item.index = idx
        item.embedding = emb
        return item

    mock_lm_studio_client.embeddings.create.return_value = Mock(
        data=[make_item(0, [0.1, 0.2]), make_item(1, [0.3, 0.4])]
    )

    result = embedder.embed_batch(["first text", "second text"])

    mock_lm_studio_client.embeddings.create.assert_called_once_with(
        input=["first text", "second text"],
        model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf",
    )
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_chunks_at_100(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    def make_item(idx):
        item = Mock()
        item.index = idx
        item.embedding = [float(idx)]
        return item

    mock_lm_studio_client.embeddings.create.side_effect = [
        Mock(data=[make_item(i) for i in range(100)]),
        Mock(data=[make_item(0)]),
    ]

    embedder.embed_batch([f"text {i}" for i in range(101)])

    assert mock_lm_studio_client.embeddings.create.call_count == 2


def test_embed_batch_strips_newlines(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    item = Mock()
    item.index = 0
    item.embedding = [0.9]
    mock_lm_studio_client.embeddings.create.return_value = Mock(data=[item])

    embedder.embed_batch(["hello\nworld"])

    mock_lm_studio_client.embeddings.create.assert_called_once_with(
        input=["hello world"],
        model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf",
    )
