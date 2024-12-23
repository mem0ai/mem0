from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.voyageai import VoyageAIEmbedding


@pytest.fixture
def mock_voyageai_client():
    with patch("mem0.embeddings.voyageai.Client") as mock_voyageai:
        mock_client = Mock()
        mock_voyageai.return_value = mock_client
        yield mock_client


def test_embed_default_model(mock_voyageai_client):
    config = BaseEmbedderConfig()
    embedder = VoyageAIEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.1, 0.2, 0.3]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Default embedder")

    mock_voyageai_client.embed.assert_called_once_with(
        texts=["Default embedder"], model="voyage-3", output_dimension=None
    )
    assert result == [0.1, 0.2, 0.3]


def test_embed_custom_model(mock_voyageai_client):
    config = BaseEmbedderConfig(model="voyage-3-large", embedding_dims=2048)
    embedder = VoyageAIEmbedding(config)
    mock_response = Mock()
    mock_response.embeddings = [[0.4, 0.5, 0.6]]
    mock_voyageai_client.embed.return_value = mock_response

    result = embedder.embed("Custom embedder")

    mock_voyageai_client.embed.assert_called_once_with(
        texts=["Custom embedder"], model="voyage-3-large", output_dimension=2048
    )
    assert result == [0.4, 0.5, 0.6]
