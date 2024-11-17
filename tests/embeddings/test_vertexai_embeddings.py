import pytest
from unittest.mock import Mock, patch
from mem0.embeddings.vertexai import VertexAIEmbedding


@pytest.fixture
def mock_text_embedding_model():
    with patch("mem0.embeddings.vertexai.TextEmbeddingModel") as mock_model:
        mock_instance = Mock()
        mock_model.from_pretrained.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def mock_os_environ():
    with patch("mem0.embeddings.vertexai.os.environ", {}) as mock_environ:
        yield mock_environ


@pytest.fixture
def mock_config():
    with patch("mem0.configs.embeddings.base.BaseEmbedderConfig") as mock_config:
        mock_config.vertex_credentials_json = None
        yield mock_config


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_default_model(mock_text_embedding_model, mock_os_environ, mock_config):
    mock_config.vertex_credentials_json = "/path/to/credentials.json"
    mock_config.return_value.model = "text-embedding-004"
    mock_config.return_value.embedding_dims = 256

    config = mock_config()
    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.1, 0.2, 0.3])
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    embedder.embed("Hello world")

    mock_text_embedding_model.from_pretrained.assert_called_once_with("text-embedding-004")
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.assert_called_once_with(
        texts=["Hello world"], output_dimensionality=256
    )


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_custom_model(mock_text_embedding_model, mock_os_environ, mock_config):
    mock_config.vertex_credentials_json = "/path/to/credentials.json"
    mock_config.return_value.model = "custom-embedding-model"
    mock_config.return_value.embedding_dims = 512

    config = mock_config()

    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.4, 0.5, 0.6])
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    result = embedder.embed("Test embedding")

    mock_text_embedding_model.from_pretrained.assert_called_with("custom-embedding-model")
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.assert_called_once_with(
        texts=["Test embedding"], output_dimensionality=512
    )

    assert result == [0.4, 0.5, 0.6]


@patch("mem0.embeddings.vertexai.os")
def test_credentials_from_environment(mock_os, mock_text_embedding_model, mock_config):
    mock_os.getenv.return_value = "/path/to/env/credentials.json"
    mock_config.vertex_credentials_json = None
    config = mock_config()
    VertexAIEmbedding(config)

    mock_os.environ.setitem.assert_not_called()


@patch("mem0.embeddings.vertexai.os")
def test_missing_credentials(mock_os, mock_text_embedding_model, mock_config):
    mock_os.getenv.return_value = None
    mock_config.return_value.vertex_credentials_json = None

    config = mock_config()

    with pytest.raises(ValueError, match="Google application credentials JSON is not provided"):
        VertexAIEmbedding(config)


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_with_different_dimensions(mock_text_embedding_model, mock_os_environ, mock_config):
    mock_config.vertex_credentials_json = "/path/to/credentials.json"
    mock_config.return_value.embedding_dims = 1024

    config = mock_config()
    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.1] * 1024)
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    result = embedder.embed("Large embedding test")

    assert result == [0.1] * 1024
