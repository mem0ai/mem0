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


def test_gemini_llm_preserves_http_client_proxies_from_base_config():
    """GeminiLLM converts BaseLlmConfig to GeminiConfig; proxies must survive.

    Regression for https://github.com/mem0ai/mem0/issues/6385 — the conversion
    block omitted http_client_proxies even though GeminiConfig accepts it and
    every other provider forwards it.
    """
    from mem0.llms.gemini import GeminiLLM

    base = BaseLlmConfig(
        model="gemini-2.0-flash",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    llm = GeminiLLM(base)
    assert llm.config.http_client_proxies == "http://proxy.local:8080"
    assert isinstance(llm.config.http_client, httpx.Client)
