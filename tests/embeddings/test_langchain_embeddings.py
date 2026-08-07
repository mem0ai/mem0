from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.langchain import LangchainEmbedding


@pytest.fixture
def mock_langchain_embeddings_class():
    with patch("mem0.embeddings.langchain.Embeddings") as mock_class:
        yield mock_class


def test_langchain_embedding_init_without_model():
    config = BaseEmbedderConfig()
    with pytest.raises(ValueError, match="`model` parameter is required"):
        LangchainEmbedding(config)


def test_langchain_embedding_init_with_invalid_model():
    config = BaseEmbedderConfig(model="not-an-embedding-instance")
    with pytest.raises(ValueError, match="`model` must be an instance of Embeddings"):
        LangchainEmbedding(config)


def test_langchain_embedding_embed(mock_langchain_embeddings_class):
    mock_model_instance = Mock(spec=mock_langchain_embeddings_class)
    mock_model_instance.embed_query.return_value = [0.1, 0.2, 0.3]
    
    config = BaseEmbedderConfig(model=mock_model_instance)
    embedder = LangchainEmbedding(config)
    
    result = embedder.embed("test text")
    
    mock_model_instance.embed_query.assert_called_once_with("test text")
    assert result == [0.1, 0.2, 0.3]
