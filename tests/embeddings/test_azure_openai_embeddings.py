import pytest
from unittest.mock import Mock, patch
from mem0.embeddings.azure_openai import AzureOpenAIEmbedding
from mem0.configs.embeddings.base import BaseEmbedderConfig


@pytest.fixture
def mock_openai_client():
    with patch("mem0.embeddings.azure_openai.AzureOpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_embed_text(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-ada-002")
    embedder = AzureOpenAIEmbedding(config)

    mock_embedding_response = Mock()
    mock_embedding_response.data = [Mock(embedding=[0.1, 0.2, 0.3])]
    mock_openai_client.embeddings.create.return_value = mock_embedding_response

    text = "Hello, this is a test."
    embedding = embedder.embed(text)

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello, this is a test."], model="text-embedding-ada-002"
    )
    assert embedding == [0.1, 0.2, 0.3]


def test_embed_text_with_newlines(mock_openai_client):
    config = BaseEmbedderConfig(model="text-embedding-ada-002")
    embedder = AzureOpenAIEmbedding(config)

    mock_embedding_response = Mock()
    mock_embedding_response.data = [Mock(embedding=[0.4, 0.5, 0.6])]
    mock_openai_client.embeddings.create.return_value = mock_embedding_response

    text = "Hello,\nthis is a test\nwith newlines."
    embedding = embedder.embed(text)

    mock_openai_client.embeddings.create.assert_called_once_with(
        input=["Hello, this is a test with newlines."], model="text-embedding-ada-002"
    )
    assert embedding == [0.4, 0.5, 0.6]
