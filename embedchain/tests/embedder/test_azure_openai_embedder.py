from unittest.mock import Mock, patch

import httpx

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.azure_openai import AzureOpenAIEmbedder

def test_with_api_version():
    config = BaseEmbedderConfig(
        model="text-embedding-ada-002",
        deployment_name="azure-deployment",
        api_version="2024-12-01-preview",
    )

    with patch("embedchain.embedder.azure_openai.AzureOpenAIEmbeddings") as mock_emb:
        emb_llm = AzureOpenAIEmbedder(config)

        mock_emb.assert_called_once_with(
            azure_endpoint="azure-deployment",
            model='text-embedding-ada-002',
            openai_api_version="2024-12-01-preview",
            dimensions=None,
            http_client=None,
            http_async_client=None,
        )

def test_embedding_dimension():
    config = BaseEmbedderConfig(
        model="text-embedding-ada-002",
        deployment_name="azure-deployment",
        vector_dimension=2048,
        api_version="2024-12-01-preview",
    )

    with patch("embedchain.embedder.azure_openai.AzureOpenAIEmbeddings") as mock_emb:
        emb_llm = AzureOpenAIEmbedder(config)

        mock_emb.assert_called_once_with(
            azure_endpoint="azure-deployment",
            model='text-embedding-ada-002',
            openai_api_version="2024-12-01-preview",
            dimensions=2048,
            http_client=None,
            http_async_client=None,
        )


def test_azure_openai_embedder_with_http_client(monkeypatch):
    mock_http_client = Mock(spec=httpx.Client)
    mock_http_client_instance = Mock(spec=httpx.Client)
    mock_http_client.return_value = mock_http_client_instance

    with patch("embedchain.embedder.azure_openai.AzureOpenAIEmbeddings") as mock_embeddings, patch(
        "httpx.Client", new=mock_http_client
    ) as mock_http_client:
        config = BaseEmbedderConfig(
            model="text-embedding-ada-002",
            deployment_name="azure-deployment",
            http_client_proxies="http://testproxy.mem0.net:8000",
        )

        _ = AzureOpenAIEmbedder(config=config)

        mock_embeddings.assert_called_once_with(
            azure_endpoint="azure-deployment",
            model='text-embedding-ada-002',
            openai_api_version="2025-01-01-preview",
            dimensions=None,
            http_client=mock_http_client_instance,
            http_async_client=None,
        )
        mock_http_client.assert_called_once_with(proxies="http://testproxy.mem0.net:8000")


def test_azure_openai_embedder_with_http_async_client(monkeypatch):
    mock_http_async_client = Mock(spec=httpx.AsyncClient)
    mock_http_async_client_instance = Mock(spec=httpx.AsyncClient)
    mock_http_async_client.return_value = mock_http_async_client_instance

    with patch("embedchain.embedder.azure_openai.AzureOpenAIEmbeddings") as mock_embeddings, patch(
        "httpx.AsyncClient", new=mock_http_async_client
    ) as mock_http_async_client:
        config = BaseEmbedderConfig(
            deployment_name="azure-deployment",
            model="text-embedding-ada-002",
            http_async_client_proxies={"http://": "http://testproxy.mem0.net:8000"},
        )

        _ = AzureOpenAIEmbedder(config=config)

        mock_embeddings.assert_called_once_with(
            azure_endpoint="azure-deployment",
            model='text-embedding-ada-002',
            openai_api_version="2025-01-01-preview",
            dimensions=None,
            http_client=None,
            http_async_client=mock_http_async_client_instance,
        )
        mock_http_async_client.assert_called_once_with(proxies={"http://": "http://testproxy.mem0.net:8000"})
