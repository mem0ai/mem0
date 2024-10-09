from unittest.mock import Mock, patch

import httpx

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.azure_openai import AzureOpenAIEmbedder


def test_azure_openai_embedder_with_http_client(monkeypatch):
    mock_http_client = Mock(spec=httpx.Client)
    mock_http_client_instance = Mock(spec=httpx.Client)
    mock_http_client.return_value = mock_http_client_instance

    with patch("embedchain.embedder.azure_openai.AzureOpenAIEmbeddings") as mock_embeddings, patch(
        "httpx.Client", new=mock_http_client
    ) as mock_http_client:
        config = BaseEmbedderConfig(
            deployment_name="text-embedding-ada-002",
            http_client_proxies="http://testproxy.mem0.net:8000",
        )

        _ = AzureOpenAIEmbedder(config=config)

        mock_embeddings.assert_called_once_with(
            deployment="text-embedding-ada-002",
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
            deployment_name="text-embedding-ada-002",
            http_async_client_proxies={"http://": "http://testproxy.mem0.net:8000"},
        )

        _ = AzureOpenAIEmbedder(config=config)

        mock_embeddings.assert_called_once_with(
            deployment="text-embedding-ada-002",
            http_client=None,
            http_async_client=mock_http_async_client_instance,
        )
        mock_http_async_client.assert_called_once_with(proxies={"http://": "http://testproxy.mem0.net:8000"})
