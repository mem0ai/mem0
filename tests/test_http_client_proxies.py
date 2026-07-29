import httpx
import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.utils.factory import LlmFactory


@pytest.mark.parametrize("config_cls", [BaseLlmConfig, BaseEmbedderConfig])
def test_config_with_string_proxy_builds_client(config_cls):
    config = config_cls(http_client_proxies="http://proxy.local:8080")
    assert isinstance(config.http_client, httpx.Client)
    assert config.http_client_proxies == "http://proxy.local:8080"


@pytest.mark.parametrize("config_cls", [BaseLlmConfig, BaseEmbedderConfig])
def test_config_with_dict_proxy_builds_client(config_cls):
    proxies = {"http://": "http://p:8080", "https://": "http://p:8080"}
    config = config_cls(http_client_proxies=proxies)
    assert isinstance(config.http_client, httpx.Client)
    assert config.http_client_proxies == proxies


@pytest.mark.parametrize("config_cls", [BaseLlmConfig, BaseEmbedderConfig])
def test_config_without_proxy_has_no_client(config_cls):
    config = config_cls()
    assert config.http_client is None
    assert config.http_client_proxies is None


def test_llm_factory_preserves_http_client_proxies():
    base = BaseLlmConfig(
        model="gpt-4o-mini",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    llm = LlmFactory.create("openai", base)
    assert llm.config.http_client_proxies == "http://proxy.local:8080"
    assert isinstance(llm.config.http_client, httpx.Client)


def test_openai_llm_forwards_http_client_to_sdk():
    from unittest.mock import patch, MagicMock

    base = BaseLlmConfig(
        model="gpt-4o-mini",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        llm = LlmFactory.create("openai", base)
        assert mock_openai.called
        kwargs = mock_openai.call_args.kwargs
        assert kwargs.get("http_client") is llm.config.http_client


def test_openai_embedding_forwards_http_client_to_sdk():
    from unittest.mock import patch, MagicMock

    from mem0.embeddings.openai import OpenAIEmbedding

    cfg = BaseEmbedderConfig(
        model="text-embedding-3-small",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    with patch("mem0.embeddings.openai.OpenAI") as mock_openai:
        mock_openai.return_value = MagicMock()
        emb = OpenAIEmbedding(cfg)
        kwargs = mock_openai.call_args.kwargs
        assert kwargs.get("http_client") is emb.config.http_client
