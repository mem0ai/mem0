from unittest.mock import Mock

import pytest

pytest.importorskip("langchain", reason="langchain not installed")

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.langchain import LangchainEmbedding

try:
    from langchain.embeddings.base import Embeddings
except ImportError:
    from unittest.mock import MagicMock

    Embeddings = MagicMock


@pytest.fixture
def mock_langchain_model():
    """Mock a Langchain embeddings model for testing."""
    mock_model = Mock(spec=Embeddings)
    mock_model.embed_query.return_value = [0.1, 0.2, 0.3]
    return mock_model


def test_langchain_initialization(mock_langchain_model):
    """LangchainEmbedding keeps the configured model instance."""
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=mock_langchain_model))

    assert embedder.langchain_model is mock_langchain_model


def test_embed_delegates_to_embed_query(mock_langchain_model):
    """embed() forwards the text to the model's embed_query and returns its vector."""
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=mock_langchain_model))

    embedding = embedder.embed("Sample text to embed.")

    mock_langchain_model.embed_query.assert_called_once_with("Sample text to embed.")
    assert embedding == [0.1, 0.2, 0.3]


def test_embed_ignores_memory_action(mock_langchain_model):
    """memory_action is accepted for interface parity and never reaches the model."""
    embedder = LangchainEmbedding(BaseEmbedderConfig(model=mock_langchain_model))

    embedder.embed("Sample text to embed.", memory_action="add")

    mock_langchain_model.embed_query.assert_called_once_with("Sample text to embed.")


def test_invalid_model():
    """A model that is not an Embeddings instance is rejected."""
    with pytest.raises(ValueError, match="`model` must be an instance of Embeddings"):
        LangchainEmbedding(BaseEmbedderConfig(model="not-a-valid-model-instance"))


def test_missing_model():
    """A missing model is rejected before any embedding call."""
    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainEmbedding(BaseEmbedderConfig(model=None))
