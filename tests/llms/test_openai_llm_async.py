import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


def _make_response(content, tool_calls=None):
    message = Mock(content=content)
    message.tool_calls = tool_calls or []
    response = Mock()
    response.choices = [Mock(message=message)]
    return response


@pytest.fixture
def openai_clients(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)

    with patch("mem0.llms.openai.OpenAI") as mock_sync_ctor, patch("mem0.llms.openai.AsyncOpenAI") as mock_async_ctor:
        sync_client = Mock()
        async_client = Mock()
        sync_client.chat = Mock(completions=Mock())
        async_client.chat = Mock(completions=Mock())
        mock_sync_ctor.return_value = sync_client
        mock_async_ctor.return_value = async_client
        yield sync_client, async_client, mock_sync_ctor, mock_async_ctor


def test_openai_clients_share_constructor_args(openai_clients):
    sync_client, async_client, sync_ctor, async_ctor = openai_clients

    llm = OpenAILLM(
        OpenAIConfig(model="gpt-4.1-nano-2025-04-14", api_key="config-key", openai_base_url="https://api.example/v1")
    )

    assert sync_ctor.call_args.kwargs == {"api_key": "config-key", "base_url": "https://api.example/v1"}
    assert async_ctor.call_args.kwargs == {"api_key": "config-key", "base_url": "https://api.example/v1"}
    assert llm.client is sync_client
    assert llm.async_client is async_client


def test_openai_async_payload_matches_sync_and_preserves_store_callback(openai_clients):
    sync_client, async_client, _, _ = openai_clients
    callback = Mock()
    llm = OpenAILLM(
        OpenAIConfig(
            model="gpt-4.1-nano-2025-04-14",
            temperature=0.7,
            max_tokens=100,
            top_p=1.0,
            store=True,
            response_callback=callback,
        )
    )
    messages = [{"role": "user", "content": "Hello"}]
    tools = [{"type": "function", "function": {"name": "noop", "parameters": {"type": "object", "properties": {}}}}]
    response_format = {"type": "json_object"}
    sync_response = _make_response("sync content")
    async_response = _make_response("sync content")
    sync_client.chat.completions.create = Mock(return_value=sync_response)
    async_client.chat.completions.create = AsyncMock(return_value=async_response)

    sync_result = llm.generate_response(
        messages,
        response_format=response_format,
        tools=tools,
        tool_choice="required",
        seed=7,
    )
    async_result = asyncio.run(
        llm.agenerate_response(
            messages,
            response_format=response_format,
            tools=tools,
            tool_choice="required",
            seed=7,
        )
    )

    expected = {
        "model": "gpt-4.1-nano-2025-04-14",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 100,
        "top_p": 1.0,
        "response_format": response_format,
        "tools": tools,
        "tool_choice": "required",
        "store": True,
        "seed": 7,
    }
    assert sync_client.chat.completions.create.call_args.kwargs == expected
    assert async_client.chat.completions.create.call_args.kwargs == expected
    assert sync_result == async_result == {"content": "sync content", "tool_calls": []}
    assert callback.call_count == 2
    assert callback.call_args_list[0].args[1] is sync_response
    assert callback.call_args_list[1].args[1] is async_response


def test_openrouter_async_payload_matches_sync_and_uses_route_fields(openai_clients, monkeypatch):
    sync_client, async_client, _, _ = openai_clients
    monkeypatch.setenv("OPENROUTER_API_KEY", "router-key")
    monkeypatch.setenv("OPENROUTER_API_BASE", "https://router.example/v1")

    llm = OpenAILLM(
        OpenAIConfig(
            model="gpt-4.1-nano-2025-04-14",
            openrouter_base_url="https://router.config/v1",
            models=["openrouter/model-a", "openrouter/model-b"],
            route="fallback",
            site_url="https://site.example",
            app_name="Mem0",
            store=True,
        )
    )
    messages = [{"role": "user", "content": "Hello"}]
    sync_response = _make_response("router content")
    async_response = _make_response("router content")
    sync_client.chat.completions.create = Mock(return_value=sync_response)
    async_client.chat.completions.create = AsyncMock(return_value=async_response)

    sync_result = llm.generate_response(messages)
    async_result = asyncio.run(llm.agenerate_response(messages))

    expected = {
        "temperature": 0.1,
        "max_tokens": 2000,
        "top_p": 0.1,
        "messages": messages,
        "models": ["openrouter/model-a", "openrouter/model-b"],
        "route": "fallback",
        "extra_headers": {"HTTP-Referer": "https://site.example", "X-Title": "Mem0"},
    }
    assert sync_client.chat.completions.create.call_args.kwargs == expected
    assert async_client.chat.completions.create.call_args.kwargs == expected
    assert "model" not in sync_client.chat.completions.create.call_args.kwargs
    assert "store" not in sync_client.chat.completions.create.call_args.kwargs
    assert sync_result == async_result == "router content"
