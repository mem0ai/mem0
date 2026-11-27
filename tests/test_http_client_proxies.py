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


def test_xai_llm_preserves_http_client_proxies_from_base_config():
    """XAILLM converts a BaseLlmConfig to XAIConfig directly; the proxy setting must survive.

    Every other provider forwards config.http_client_proxies in this conversion. xAI
    forwarded the already-built config.http_client instead, which build_http_client then
    tried to treat as a proxy, crashing whenever a proxy was configured.
    """
    from mem0.llms.xai import XAILLM

    base = BaseLlmConfig(
        model="grok-4",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    llm = XAILLM(base)
    assert llm.config.http_client_proxies == "http://proxy.local:8080"
    assert isinstance(llm.config.http_client, httpx.Client)
