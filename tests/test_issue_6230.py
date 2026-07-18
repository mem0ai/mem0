from pathlib import Path
from unittest.mock import MagicMock
import importlib
import sys
import types

mem0_module = types.ModuleType("mem0")
mem0_module.__path__ = [str(Path(__file__).resolve().parents[1] / "mem0")]
sys.modules.setdefault("mem0", mem0_module)

base_config = importlib.import_module("mem0.configs.llms.base")
xai_llm = importlib.import_module("mem0.llms.xai")
BaseLlmConfig = base_config.BaseLlmConfig
XAILLM = xai_llm.XAILLM


def test_issue_6230(monkeypatch):
    proxy_url = "http://proxy.local:8080"
    built_client = object()
    seen_proxies = []

    def fake_build_http_client(http_client_proxies):
        seen_proxies.append(http_client_proxies)
        if http_client_proxies is built_client:
            raise TypeError("built http client was forwarded as proxy config")
        if http_client_proxies == proxy_url:
            return built_client
        return None

    monkeypatch.setattr(base_config, "build_http_client", fake_build_http_client)
    monkeypatch.setattr(xai_llm, "OpenAI", MagicMock())

    base = BaseLlmConfig(model="grok-4", api_key="sk-test", http_client_proxies=proxy_url)

    llm = XAILLM(base)

    assert llm.config.http_client_proxies == proxy_url
    assert llm.config.http_client is built_client
    assert seen_proxies == [proxy_url, proxy_url]
