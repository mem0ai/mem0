from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.together import TogetherEmbedding

DEFAULT_MODEL = "intfloat/multilingual-e5-large-instruct"
DEFAULT_EMBEDDING_DIMS = 1024


@pytest.fixture
def mock_together_client():
    with patch("mem0.embeddings.together.Together") as mock_together:
        mock_client = Mock()
        mock_together.return_value = mock_client
        yield mock_client


def test_embed_text(mock_together_client):
    config = BaseEmbedderConfig(model=DEFAULT_MODEL, embedding_dims=DEFAULT_EMBEDDING_DIMS)
    embedder = TogetherEmbedding(config)

    mock_together_client.embeddings.create.return_value = Mock(data=[Mock(embedding=[0.1, 0.2, 0.3, 0.4, 0.5])])

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_together_client.embeddings.create.assert_called_once_with(model=DEFAULT_MODEL, input=text)
    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_embed_batch_single_call(mock_together_client):
    config = BaseEmbedderConfig(model=DEFAULT_MODEL, embedding_dims=DEFAULT_EMBEDDING_DIMS)
    embedder = TogetherEmbedding(config)

    mock_item0 = Mock(index=0, embedding=[0.1, 0.2, 0.3])
    mock_item1 = Mock(index=1, embedding=[0.4, 0.5, 0.6])
    mock_together_client.embeddings.create.return_value = Mock(data=[mock_item0, mock_item1])

    texts = ["First text.", "Second text."]
    embeddings = embedder.embed_batch(texts)

    mock_together_client.embeddings.create.assert_called_once_with(model=DEFAULT_MODEL, input=texts)
    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]


def test_embed_batch_empty_list(mock_together_client):
    config = BaseEmbedderConfig(model=DEFAULT_MODEL, embedding_dims=DEFAULT_EMBEDDING_DIMS)
    embedder = TogetherEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_together_client.embeddings.create.assert_not_called()


def test_embed_batch_count_mismatch_raises(mock_together_client):
    config = BaseEmbedderConfig(model=DEFAULT_MODEL, embedding_dims=DEFAULT_EMBEDDING_DIMS)
    embedder = TogetherEmbedding(config)

    mock_item0 = Mock(index=0, embedding=[0.1, 0.2, 0.3])
    mock_together_client.embeddings.create.return_value = Mock(data=[mock_item0])

    with pytest.raises(ValueError, match="returned 1 embeddings for 2 texts"):
        embedder.embed_batch(["first text", "second text"])


def test_default_config_applies_together_defaults(mock_together_client):
    embedder = TogetherEmbedding(BaseEmbedderConfig())

    assert embedder.config.model == DEFAULT_MODEL
    assert embedder.config.embedding_dims == DEFAULT_EMBEDDING_DIMS


def test_explicit_config_overrides_defaults(mock_together_client):
    # The `config.x or default` wiring must honor user-provided values, not clobber them.
    config = BaseEmbedderConfig(model="BAAI/bge-base-en-v1.5", embedding_dims=768)
    embedder = TogetherEmbedding(config)

    assert embedder.config.model == "BAAI/bge-base-en-v1.5"
    assert embedder.config.embedding_dims == 768

    # ...and the chosen model actually reaches the Together API call.
    mock_together_client.embeddings.create.return_value = Mock(data=[Mock(embedding=[0.0] * 768)])
    embedder.embed("hello")
    mock_together_client.embeddings.create.assert_called_once_with(model="BAAI/bge-base-en-v1.5", input="hello")
