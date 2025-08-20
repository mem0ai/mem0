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


@pytest.fixture
def base_embedder_config():
    class DummyAzureKwargs:
        api_key = None
        azure_deployment = None
        azure_endpoint = None
        api_version = None
        default_headers = None

    class DummyConfig(BaseEmbedderConfig):
        azure_kwargs = DummyAzureKwargs()
        http_client = None
        model = "test-model"

    return DummyConfig()


def test_init_with_api_key(monkeypatch, base_embedder_config):
    base_embedder_config.azure_kwargs.api_key = "test-key"
    base_embedder_config.azure_kwargs.azure_deployment = "test-deployment"
    base_embedder_config.azure_kwargs.azure_endpoint = "https://test.endpoint"
    base_embedder_config.azure_kwargs.api_version = "2024-01-01"
    base_embedder_config.azure_kwargs.default_headers = {"X-Test": "Header"}

    with (
        patch("mem0.embeddings.azure_openai.AzureOpenAI") as mock_azure_openai,
        patch("mem0.embeddings.azure_openai.DefaultAzureCredential") as mock_cred,
        patch("mem0.embeddings.azure_openai.get_bearer_token_provider") as mock_token_provider,
    ):
        AzureOpenAIEmbedding(base_embedder_config)
        mock_azure_openai.assert_called_once_with(
            azure_deployment="test-deployment",
            azure_endpoint="https://test.endpoint",
            azure_ad_token_provider=None,
            api_version="2024-01-01",
            api_key="test-key",
            http_client=None,
            default_headers={"X-Test": "Header"},
        )
        mock_cred.assert_not_called()
        mock_token_provider.assert_not_called()


def test_init_with_env_vars(monkeypatch, base_embedder_config):
    monkeypatch.setenv("EMBEDDING_AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("EMBEDDING_AZURE_DEPLOYMENT", "env-deployment")
    monkeypatch.setenv("EMBEDDING_AZURE_ENDPOINT", "https://env.endpoint")
    monkeypatch.setenv("EMBEDDING_AZURE_API_VERSION", "2024-02-02")

    with patch("mem0.embeddings.azure_openai.AzureOpenAI") as mock_azure_openai:
        AzureOpenAIEmbedding(base_embedder_config)
        mock_azure_openai.assert_called_once_with(
            azure_deployment="env-deployment",
            azure_endpoint="https://env.endpoint",
            azure_ad_token_provider=None,
            api_version="2024-02-02",
            api_key="env-key",
            http_client=None,
            default_headers=None,
        )


def test_init_with_default_azure_credential(monkeypatch, base_embedder_config):
    base_embedder_config.azure_kwargs.api_key = ""
    with (
        patch("mem0.embeddings.azure_openai.DefaultAzureCredential") as mock_cred,
        patch("mem0.embeddings.azure_openai.get_bearer_token_provider") as mock_token_provider,
        patch("mem0.embeddings.azure_openai.AzureOpenAI") as mock_azure_openai,
    ):
        mock_cred_instance = Mock()
        mock_cred.return_value = mock_cred_instance
        mock_token_provider_instance = Mock()
        mock_token_provider.return_value = mock_token_provider_instance

        AzureOpenAIEmbedding(base_embedder_config)
        mock_cred.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_cred_instance, "https://cognitiveservices.azure.com/.default")
        mock_azure_openai.assert_called_once_with(
            azure_deployment=None,
            azure_endpoint=None,
            azure_ad_token_provider=mock_token_provider_instance,
            api_version=None,
            api_key=None,
            http_client=None,
            default_headers=None,
        )


def test_init_with_placeholder_api_key(monkeypatch, base_embedder_config):
    base_embedder_config.azure_kwargs.api_key = "your-api-key"
    with (
        patch("mem0.embeddings.azure_openai.DefaultAzureCredential") as mock_cred,
        patch("mem0.embeddings.azure_openai.get_bearer_token_provider") as mock_token_provider,
        patch("mem0.embeddings.azure_openai.AzureOpenAI") as mock_azure_openai,
    ):
        mock_cred_instance = Mock()
        mock_cred.return_value = mock_cred_instance
        mock_token_provider_instance = Mock()
        mock_token_provider.return_value = mock_token_provider_instance

        AzureOpenAIEmbedding(base_embedder_config)
        mock_cred.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_cred_instance, "https://cognitiveservices.azure.com/.default")
        mock_azure_openai.assert_called_once_with(
            azure_deployment=None,
            azure_endpoint=None,
            azure_ad_token_provider=mock_token_provider_instance,
            api_version=None,
            api_key=None,
            http_client=None,
            default_headers=None,
        )
