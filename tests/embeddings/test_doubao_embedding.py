import pytest
from unittest.mock import Mock, patch

from mem0.embeddings.doubao import DouBaoEmbedding
from mem0.configs.embeddings.base import BaseEmbedderConfig


@pytest.fixture
def mock_doubao_client():
    with patch("mem0.embeddings.doubao.Ark") as mock_ark:
        mock_client = Mock()
        mock_ark.return_value = mock_client
        yield mock_client

def test_embed_custom_model_and_without_api_key_env(mock_doubao_client):
    model = "your endpoint"
    api_key = "your_api_key"
    config = BaseEmbedderConfig(model=model, api_key=api_key, embedding_dims=2048)
    embedder = DouBaoEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_doubao_client.embeddings.create.return_value = mock_response
    result = embedder.embed("Test embedding")
    mock_doubao_client.embeddings.create.assert_called_once_with(
        input=["Test embedding"], model=model
    )
    assert result == [0.4, 0.5, 0.6]

def test_embed_uses_environment_api_key(mock_doubao_client, monkeypatch):
    model = "your endpoint"
    monkeypatch.setenv("ARK_API_KEY", "env_key")
    config = BaseEmbedderConfig(model=model)
    embedder = DouBaoEmbedding(config)
    mock_response = Mock()
    mock_response.data = [Mock(embedding=[1.3, 1.4, 1.5])]
    mock_doubao_client.embeddings.create.return_value = mock_response

    result = embedder.embed("Environment key test")

    mock_doubao_client.embeddings.create.assert_called_once_with(
        input=["Environment key test"], model=model
    )
    assert result == [1.3, 1.4, 1.5]
