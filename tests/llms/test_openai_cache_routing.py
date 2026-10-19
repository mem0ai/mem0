from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM

MESSAGES = [{"role": "user", "content": "hi"}]


def make_llm(base_url, monkeypatch, **config):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with patch("mem0.llms.openai.OpenAI") as client_class:
        client = Mock()
        client.base_url = base_url
        client.chat.completions.create.return_value = Mock(choices=[Mock(message=Mock(content="ok"))])
        client_class.return_value = client
        llm = OpenAILLM(OpenAIConfig(model="m", api_key="k", openai_base_url=base_url, **config))
    return llm, client


def sent(client):
    return client.chat.completions.create.call_args.kwargs


def test_no_key_sends_nothing(monkeypatch):
    llm, client = make_llm("https://api.x.ai/v1", monkeypatch)
    llm.generate_response(MESSAGES)
    assert "extra_headers" not in sent(client)
    assert "extra_body" not in sent(client)


def test_auto_uses_xai_header(monkeypatch):
    llm, client = make_llm("https://api.x.ai/v1", monkeypatch, cache_routing_key="user-42")
    llm.generate_response(MESSAGES)
    assert sent(client)["extra_headers"] == {"x-grok-conv-id": "user-42"}
    assert "extra_body" not in sent(client)


def test_auto_openai_host_uses_prompt_cache_key(monkeypatch):
    llm, client = make_llm("https://api.openai.com/v1", monkeypatch, cache_routing_key="user-42")
    llm.generate_response(MESSAGES)
    assert sent(client)["extra_body"] == {"prompt_cache_key": "user-42"}
    assert "extra_headers" not in sent(client)


def test_auto_regional_xai_host_uses_header(monkeypatch):
    llm, client = make_llm("https://us-east-1.api.x.ai/v1", monkeypatch, cache_routing_key="user-42")
    llm.generate_response(MESSAGES)
    assert sent(client)["extra_headers"] == {"x-grok-conv-id": "user-42"}


def test_auto_unknown_host_sends_nothing(monkeypatch):
    llm, client = make_llm("https://api.groq.com/openai/v1", monkeypatch, cache_routing_key="user-42")
    llm.generate_response(MESSAGES)
    assert "extra_headers" not in sent(client)
    assert "extra_body" not in sent(client)


def test_auto_lookalike_host_sends_nothing(monkeypatch):
    llm, client = make_llm("https://evilapi.x.ai/v1", monkeypatch, cache_routing_key="user-42")
    llm.generate_response(MESSAGES)
    assert "extra_headers" not in sent(client)
    assert "extra_body" not in sent(client)


def test_forced_prompt_cache_key_on_other_host(monkeypatch):
    llm, client = make_llm(
        "https://api.groq.com/openai/v1", monkeypatch, cache_routing_key="k2", cache_routing="prompt_cache_key"
    )
    llm.generate_response(MESSAGES)
    assert sent(client)["extra_body"] == {"prompt_cache_key": "k2"}


def test_forced_mode(monkeypatch):
    llm, client = make_llm(
        "https://example.test/v1", monkeypatch, cache_routing_key="k1", cache_routing="x-grok-conv-id"
    )
    llm.generate_response(MESSAGES)
    assert sent(client)["extra_headers"] == {"x-grok-conv-id": "k1"}


def test_rejects_unknown_mode():
    with pytest.raises(ValueError):
        OpenAIConfig(cache_routing="bogus")
