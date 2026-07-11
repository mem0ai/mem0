"""Unit tests for LangchainEmbedding (issue #6095).

Avoid constructors that do ``Mock(spec=<another Mock>)`` — that raises
``InvalidSpecError`` under Python 3.11+ (this is what broke #6096).
"""

from unittest.mock import Mock

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.langchain import LangchainEmbedding


class _FakeEmbeddings:
    """Stand-in for langchain.embeddings.base.Embeddings."""

    def embed_query(self, text):
        return [0.1, 0.2, 0.3]


def test_langchain_embedding_init_without_model():
    config = BaseEmbedderConfig()
    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainEmbedding(config)


def test_langchain_embedding_init_with_invalid_model():
    config = BaseEmbedderConfig(model="not-an-embedding-instance")
    with pytest.raises(ValueError, match="`model` must be an instance of Embeddings"):
        LangchainEmbedding(config)


def test_langchain_embedding_embed(monkeypatch):
    # Patch the symbol LangchainEmbedding validates against so our fake
    # is accepted without importing a real langchain graph of types.
    monkeypatch.setattr("mem0.embeddings.langchain.Embeddings", _FakeEmbeddings)

    model = _FakeEmbeddings()
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=model))
    result = embedder.embed("test text")
    assert result == [0.1, 0.2, 0.3]


def test_langchain_embedding_embed_batch_default(monkeypatch):
    """Default embed_batch iterates embed(); verify that path works for LangchainEmbedding."""
    monkeypatch.setattr("mem0.embeddings.langchain.Embeddings", _FakeEmbeddings)

    model = Mock(spec=_FakeEmbeddings)
    model.embed_query.side_effect = lambda text: [float(len(text)), 0.0]

    embedder = LangchainEmbedding(BaseEmbedderConfig(model=model))
    results = embedder.embed_batch(["a", "bb", "ccc"])
    assert results == [[1.0, 0.0], [2.0, 0.0], [3.0, 0.0]]
    assert model.embed_query.call_count == 3
