from unittest.mock import Mock

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig

try:
    from langchain.embeddings.base import Embeddings

    from mem0.embeddings.langchain import LangchainEmbedding
except ImportError:
    pytest.skip("langchain not installed", allow_module_level=True)


@pytest.fixture
def mock_langchain_model():
    """Create a mock Langchain Embeddings instance that passes isinstance checks."""
    mock_model = Mock(spec=Embeddings)
    yield mock_model


def test_embed_batch_uses_embed_documents(mock_langchain_model):
    """embed_batch() should delegate to Langchain's embed_documents()."""
    config = BaseEmbedderConfig(model=mock_langchain_model)
    embedder = LangchainEmbedding(config)

    mock_langchain_model.embed_documents.return_value = [
        [0.1, 0.2, 0.3],
        [0.4, 0.5, 0.6],
        [0.7, 0.8, 0.9],
    ]

    texts = ["First text.", "Second text.", "Third text."]
    embeddings = embedder.embed_batch(texts)

    mock_langchain_model.embed_documents.assert_called_once_with(texts)
    assert embeddings == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6], [0.7, 0.8, 0.9]]


def test_embed_batch_empty_list(mock_langchain_model):
    """embed_batch() with an empty list should return [] without calling the model."""
    config = BaseEmbedderConfig(model=mock_langchain_model)
    embedder = LangchainEmbedding(config)

    result = embedder.embed_batch([])

    assert result == []
    mock_langchain_model.embed_documents.assert_not_called()


def test_embed_batch_single_text(mock_langchain_model):
    """embed_batch() with a single text should still use embed_documents()."""
    config = BaseEmbedderConfig(model=mock_langchain_model)
    embedder = LangchainEmbedding(config)

    mock_langchain_model.embed_documents.return_value = [[0.1, 0.2, 0.3]]

    embeddings = embedder.embed_batch(["Only text."])

    mock_langchain_model.embed_documents.assert_called_once_with(["Only text."])
    assert embeddings == [[0.1, 0.2, 0.3]]


def test_embed_single_uses_embed_query(mock_langchain_model):
    """embed() should delegate to Langchain's embed_query()."""
    config = BaseEmbedderConfig(model=mock_langchain_model)
    embedder = LangchainEmbedding(config)

    mock_langchain_model.embed_query.return_value = [0.1, 0.2, 0.3]

    embedding = embedder.embed("Test text.")

    mock_langchain_model.embed_query.assert_called_once_with("Test text.")
    assert embedding == [0.1, 0.2, 0.3]
