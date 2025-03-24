import pytest
from unittest.mock import Mock, patch
from mem0.embeddings.lmstudio import LMStudioEmbedding
from mem0.configs.embeddings.base import BaseEmbedderConfig


@pytest.fixture
def mock_lm_studio_client():
    with patch("mem0.embeddings.lmstudio.Client") as mock_lm_studio:
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"}]}
        mock_lm_studio.return_value = mock_client
        yield mock_client


def test_embed_text(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    mock_response = {"embedding": [0.1, 0.2, 0.3, 0.4, 0.5]}
    mock_lm_studio_client.embeddings.return_value = mock_response

    text = "Sample text to embed."
    embedding = embedder.embed(text)

    mock_lm_studio_client.embeddings.assert_called_once_with(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", prompt=text)

    assert embedding == [0.1, 0.2, 0.3, 0.4, 0.5]


def test_ensure_model_exists(mock_lm_studio_client):
    config = BaseEmbedderConfig(model="nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf", embedding_dims=512)
    embedder = LMStudioEmbedding(config)

    mock_lm_studio_client.pull.assert_not_called()

    mock_lm_studio_client.list.return_value = {"models": []}

    embedder._ensure_model_exists()

    mock_lm_studio_client.pull.assert_called_once_with("nomic-embed-text")
