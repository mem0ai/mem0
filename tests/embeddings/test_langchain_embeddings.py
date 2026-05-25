from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig

try:
    from mem0.embeddings.langchain import LangchainEmbedding
except ImportError:
    pytest.skip("langchain not installed", allow_module_level=True)


def make_langchain_embedder():
    mock_lc_model = Mock()
    config = BaseEmbedderConfig(model=mock_lc_model)
    with patch("mem0.embeddings.langchain.Embeddings", Mock):
        embedder = LangchainEmbedding(config)
    return embedder, mock_lc_model


def test_embed_calls_embed_query():
    embedder, mock_lc_model = make_langchain_embedder()
    mock_lc_model.embed_query.return_value = [0.1, 0.2, 0.3]

    result = embedder.embed("hello world")

    mock_lc_model.embed_query.assert_called_once_with("hello world")
    assert result == [0.1, 0.2, 0.3]


def test_embed_batch_calls_embed_documents():
    embedder, mock_lc_model = make_langchain_embedder()
    mock_lc_model.embed_documents.return_value = [[0.1, 0.2], [0.3, 0.4]]

    result = embedder.embed_batch(["first", "second"])

    mock_lc_model.embed_documents.assert_called_once_with(["first", "second"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_single_api_call():
    embedder, mock_lc_model = make_langchain_embedder()
    mock_lc_model.embed_documents.return_value = [[float(i)] for i in range(50)]

    embedder.embed_batch([f"text {i}" for i in range(50)])

    assert mock_lc_model.embed_documents.call_count == 1


def test_embed_batch_memory_action_ignored():
    """LangChain's embed_documents has no concept of memory_action — it should be accepted but not forwarded."""
    embedder, mock_lc_model = make_langchain_embedder()
    mock_lc_model.embed_documents.return_value = [[0.5, 0.6]]

    embedder.embed_batch(["query text"], memory_action="search")

    mock_lc_model.embed_documents.assert_called_once_with(["query text"])


def test_init_requires_model():
    config = BaseEmbedderConfig(model=None)
    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainEmbedding(config)


def test_init_requires_embeddings_instance():
    config = BaseEmbedderConfig(model="not-an-embeddings-instance")
    with pytest.raises(ValueError, match="`model` must be an instance of Embeddings"):
        LangchainEmbedding(config)
