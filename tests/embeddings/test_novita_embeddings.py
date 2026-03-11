from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.novita import NovitaEmbeddingConfig
from mem0.embeddings.novita import NovitaEmbedding


@pytest.fixture
def mock_novita_client():
    with patch("mem0.embeddings.novita.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_novita_embed_default_model_and_dims(mock_novita_client):
    embedder = NovitaEmbedding(NovitaEmbeddingConfig(api_key="test_key"))
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2])]
    mock_novita_client.embeddings.create.return_value = mock_response

    embedder.embed("hello")

    mock_novita_client.embeddings.create.assert_called_once_with(
        input=["hello"],
        model="qwen/qwen3-embedding-0.6b",
        dimensions=1024,
    )


def test_novita_embed_custom_model_and_dims(mock_novita_client):
    config = NovitaEmbeddingConfig(model="custom/model", embedding_dims=512, api_key="test_key")
    embedder = NovitaEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.1, 0.2])]
    mock_novita_client.embeddings.create.return_value = mock_response

    embedder.embed("hello")

    mock_novita_client.embeddings.create.assert_called_once_with(
        input=["hello"],
        model="custom/model",
        dimensions=512,
    )
