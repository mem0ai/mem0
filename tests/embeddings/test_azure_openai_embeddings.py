from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.azure_openai import AzureOpenAIEmbedding


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


@pytest.mark.parametrize(
    "default_headers, expected_header",
    [(None, None), ({"Test": "test_value"}, "test_value"), ({}, None)],
)
def test_embed_text_with_default_headers(default_headers, expected_header):
    config = BaseEmbedderConfig(
        model="text-embedding-ada-002",
        azure_kwargs={
            "api_key": "test",
            "api_version": "test_version",
            "azure_endpoint": "test_endpoint",
            "azuer_deployment": "test_deployment",
            "default_headers": default_headers,
        },
    )
    embedder = AzureOpenAIEmbedding(config)
    assert embedder.client.api_key == "test"
    assert embedder.client._api_version == "test_version"
    assert embedder.client.default_headers.get("Test") == expected_header
