import pytest
from unittest.mock import Mock, patch
from mem0.embeddings.huggingface import HuggingFaceEmbedding
from mem0.configs.embeddings.base import BaseEmbedderConfig


@pytest.fixture
def mock_sentence_transformer():
    with patch("mem0.embeddings.huggingface.SentenceTransformer") as mock_transformer:
        mock_model = Mock()
        mock_transformer.return_value = mock_model
        yield mock_model


def test_embed_default_model(mock_sentence_transformer):
    config = BaseEmbedderConfig()
    embedder = HuggingFaceEmbedding(config)

    mock_sentence_transformer.encode.return_value = [0.1, 0.2, 0.3]
    result = embedder.embed("Hello world")

    mock_sentence_transformer.encode.assert_called_once_with("Hello world")

    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_sentence_transformer):
    config = BaseEmbedderConfig(model="paraphrase-MiniLM-L6-v2")
    embedder = HuggingFaceEmbedding(config)

    mock_sentence_transformer.encode.return_value = [0.4, 0.5, 0.6]
    result = embedder.embed("Custom model test")

    mock_sentence_transformer.encode.assert_called_once_with("Custom model test")

    assert result == [0.4, 0.5, 0.6]


def test_embed_with_model_kwargs(mock_sentence_transformer):
    config = BaseEmbedderConfig(model="all-MiniLM-L6-v2", model_kwargs={"device": "cuda"})
    embedder = HuggingFaceEmbedding(config)

    mock_sentence_transformer.encode.return_value = [0.7, 0.8, 0.9]
    result = embedder.embed("Test with device")

    mock_sentence_transformer.encode.assert_called_once_with("Test with device")

    assert result == [0.7, 0.8, 0.9]


def test_embed_sets_embedding_dims(mock_sentence_transformer):
    config = BaseEmbedderConfig()

    mock_sentence_transformer.get_sentence_embedding_dimension.return_value = 384
    embedder = HuggingFaceEmbedding(config)

    assert embedder.config.embedding_dims == 384
    mock_sentence_transformer.get_sentence_embedding_dimension.assert_called_once()


def test_embed_with_custom_embedding_dims(mock_sentence_transformer):
    config = BaseEmbedderConfig(model="all-mpnet-base-v2", embedding_dims=768)
    embedder = HuggingFaceEmbedding(config)

    mock_sentence_transformer.encode.return_value = [1.0, 1.1, 1.2]
    result = embedder.embed("Custom embedding dims")

    mock_sentence_transformer.encode.assert_called_once_with("Custom embedding dims")

    assert embedder.config.embedding_dims == 768

    assert result == [1.0, 1.1, 1.2]
