"""Regression tests for HTTP proxy support in LLM/embedding configs.

Covers two bugs:
1. `httpx.Client(proxies=...)` was removed in httpx >= 0.28, so building any
   config with a proxy raised TypeError.
2. `LlmFactory` passed the already-built `http_client` where the raw
   `http_client_proxies` value was expected when converting a BaseLlmConfig to a
   provider-specific config, silently dropping the user's proxy setting.
"""

import httpx
import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.utils.factory import LlmFactory


@pytest.mark.parametrize("config_cls", [BaseLlmConfig, BaseEmbedderConfig])
def test_config_with_string_proxy_builds_client(config_cls):
    config = config_cls(http_client_proxies="http://proxy.local:8080")
    assert isinstance(config.http_client, httpx.Client)
    # The raw value is preserved (not only the built client).
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
    # Converting a BaseLlmConfig to a provider config must pass the raw proxies
    # value through, not the constructed httpx.Client object.
    base = BaseLlmConfig(
        model="gpt-4o-mini",
        api_key="sk-test",
        http_client_proxies="http://proxy.local:8080",
    )
    llm = LlmFactory.create("openai", base)
    assert llm.config.http_client_proxies == "http://proxy.local:8080"
    assert isinstance(llm.config.http_client, httpx.Client)
