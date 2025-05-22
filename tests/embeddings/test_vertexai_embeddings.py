from unittest.mock import Mock, patch

import pytest

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
        mock_config.return_value.vertex_credentials_json = "/path/to/credentials.json"
        yield mock_config


@pytest.fixture
def mock_embedding_types():
    return [
        "SEMANTIC_SIMILARITY",
        "CLASSIFICATION",
        "CLUSTERING",
        "RETRIEVAL_DOCUMENT",
        "RETRIEVAL_QUERY",
        "QUESTION_ANSWERING",
        "FACT_VERIFICATION",
        "CODE_RETRIEVAL_QUERY",
    ]


@pytest.fixture
def mock_text_embedding_input():
    with patch("mem0.embeddings.vertexai.TextEmbeddingInput") as mock_input:
        yield mock_input


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_default_model(mock_text_embedding_model, mock_os_environ, mock_config, mock_text_embedding_input):
    mock_config.return_value.model = "text-embedding-004"
    mock_config.return_value.embedding_dims = 256

    config = mock_config()
    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.1, 0.2, 0.3])
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    embedder.embed("Hello world")
    mock_text_embedding_input.assert_called_once_with(text="Hello world", task_type="SEMANTIC_SIMILARITY")
    mock_text_embedding_model.from_pretrained.assert_called_once_with("text-embedding-004")

    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.assert_called_once_with(
        texts=[mock_text_embedding_input("Hello world")], output_dimensionality=256
    )


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_custom_model(mock_text_embedding_model, mock_os_environ, mock_config, mock_text_embedding_input):
    mock_config.return_value.model = "custom-embedding-model"
    mock_config.return_value.embedding_dims = 512

    config = mock_config()

    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.4, 0.5, 0.6])
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    result = embedder.embed("Test embedding")
    mock_text_embedding_input.assert_called_once_with(text="Test embedding", task_type="SEMANTIC_SIMILARITY")
    mock_text_embedding_model.from_pretrained.assert_called_with("custom-embedding-model")
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.assert_called_once_with(
        texts=[mock_text_embedding_input("Test embedding")], output_dimensionality=512
    )

    assert result == [0.4, 0.5, 0.6]


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_embed_with_memory_action(
    mock_text_embedding_model, mock_os_environ, mock_config, mock_embedding_types, mock_text_embedding_input
):
    mock_config.return_value.model = "text-embedding-004"
    mock_config.return_value.embedding_dims = 256

    for embedding_type in mock_embedding_types:
        mock_config.return_value.memory_add_embedding_type = embedding_type
        mock_config.return_value.memory_update_embedding_type = embedding_type
        mock_config.return_value.memory_search_embedding_type = embedding_type

        config = mock_config()
        embedder = VertexAIEmbedding(config)

        mock_text_embedding_model.from_pretrained.assert_called_with("text-embedding-004")

        for memory_action in ["add", "update", "search"]:
            embedder.embed("Hello world", memory_action=memory_action)

            mock_text_embedding_input.assert_called_with(text="Hello world", task_type=embedding_type)
            mock_text_embedding_model.from_pretrained.return_value.get_embeddings.assert_called_with(
                texts=[mock_text_embedding_input("Hello world", embedding_type)], output_dimensionality=256
            )


@patch("mem0.embeddings.vertexai.os")
def test_credentials_from_environment(mock_os, mock_text_embedding_model, mock_config):
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
    mock_config.return_value.embedding_dims = 1024

    config = mock_config()
    embedder = VertexAIEmbedding(config)

    mock_embedding = Mock(values=[0.1] * 1024)
    mock_text_embedding_model.from_pretrained.return_value.get_embeddings.return_value = [mock_embedding]

    result = embedder.embed("Large embedding test")

    assert result == [0.1] * 1024


@patch("mem0.embeddings.vertexai.TextEmbeddingModel")
def test_invalid_memory_action(mock_text_embedding_model, mock_config):
    mock_config.return_value.model = "text-embedding-004"
    mock_config.return_value.embedding_dims = 256

    config = mock_config()
    embedder = VertexAIEmbedding(config)

    with pytest.raises(ValueError):
        embedder.embed("Hello world", memory_action="invalid_action")
