import json
import os
from unittest.mock import Mock, patch

import httpx
import pytest
from openai import OpenAI

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_openai_llm_base_url():
    # case1: default config: with openai official base url
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == "https://api.openai.com/v1/"

    # case2: with env variable OPENAI_API_BASE
    provider_base_url = "https://api.provider.com/v1"
    os.environ["OPENAI_BASE_URL"] = provider_base_url
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == provider_base_url + "/"

    # case3: with config.openai_base_url
    config_base_url = "https://api.config.com/v1"
    config = OpenAIConfig(
        model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key", openai_base_url=config_base_url
    )
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == config_base_url + "/"


def test_generate_response_without_tools(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Add a new memory: Today is a sunny day."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_memory",
                "description": "Add a memory",
                "parameters": {
                    "type": "object",
                    "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
                    "required": ["data"],
                },
            },
        }
    ]

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "I've added the memory for you."

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "Today is a sunny day."}'

    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools, tool_choice="auto"
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_response_callback_invocation(mock_openai_client):
    # Setup mock callback
    mock_callback = Mock()
    
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", response_callback=mock_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test callback"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Call method
    llm.generate_response(messages)
    
    # Verify callback called with correct arguments
    mock_callback.assert_called_once()
    args = mock_callback.call_args[0]
    assert args[0] is llm  # llm_instance
    assert args[1] == mock_response  # raw_response
    assert "messages" in args[2]  # params


def test_no_response_callback(mock_openai_client):
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14")
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test no callback"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Should complete without calling any callback
    response = llm.generate_response(messages)
    assert response == "Response"
    
    # Verify no callback is set
    assert llm.config.response_callback is None


def test_callback_exception_handling(mock_openai_client):
    # Callback that raises exception
    def faulty_callback(*args):
        raise ValueError("Callback error")
    
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", response_callback=faulty_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test exception"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Expected response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Should complete without raising
    response = llm.generate_response(messages)
    assert response == "Expected response"
    
    # Verify callback was called (even though it raised an exception)
    assert llm.config.response_callback is faulty_callback


def test_reasoning_model_with_reasoning_effort(mock_openai_client):
    """Test that reasoning_effort is passed to the API for reasoning models."""
    config = OpenAIConfig(model="o3-mini", reasoning_effort="low")
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response from o3-mini"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert call_kwargs[1]["reasoning_effort"] == "low"
    assert "temperature" not in call_kwargs[1]  # reasoning models don't get temperature
    assert response == "Response from o3-mini"


def test_reasoning_model_without_reasoning_effort(mock_openai_client):
    """Test that reasoning_effort is not passed when not configured."""
    config = OpenAIConfig(model="o3-mini")
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert "reasoning_effort" not in call_kwargs[1]


def test_non_reasoning_model_ignores_reasoning_effort(mock_openai_client):
    """Test that reasoning_effort is not passed for non-reasoning models."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", reasoning_effort="high")
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    # Non-reasoning models use common params path, reasoning_effort not added there
    assert "reasoning_effort" not in call_kwargs[1]


def test_reasoning_effort_config_values():
    """Test that reasoning_effort can be set to all valid values."""
    for effort in ["low", "medium", "high"]:
        config = OpenAIConfig(model="o3", reasoning_effort=effort)
        assert config.reasoning_effort == effort

    config = OpenAIConfig(model="o3")
    assert config.reasoning_effort is None


def test_store_not_sent_by_default(mock_openai_client):
    """`store` must NOT be injected into requests when the user has not
    explicitly configured it. Regression test for issue #4709, where
    `store=False` was unconditionally sent and rejected by OpenAI-compatible
    backends such as Google Gemini."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.1)
    assert config.store is None  # new opt-in default
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert "store" not in call_kwargs


def test_store_sent_when_explicitly_true(mock_openai_client):
    """When the user explicitly sets `store=True`, the field must be forwarded."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", store=True)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["store"] is True


def test_store_sent_when_explicitly_false(mock_openai_client):
    """When the user explicitly sets `store=False`, the field must still be
    forwarded — explicit opt-out is a valid configuration for users who rely on
    it for OpenAI's zero-data-retention behavior."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", store=False)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["store"] is False


def test_gpt5_mini_not_classified_as_reasoning(mock_openai_client):
    """Test that gpt-5.4-mini is NOT treated as a reasoning model.

    gpt-5.4-mini supports temperature and other standard params.
    The previous substring match on "gpt-5" incorrectly stripped these.
    Regression test for https://github.com/mem0ai/mem0/issues/4738
    """
    config = OpenAIConfig(model="gpt-5.4-mini", temperature=0.1)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    # gpt-5.4-mini should pass through temperature, not strip it
    assert call_kwargs[1].get("temperature") == 0.1


def test_is_reasoning_model_classification(mock_openai_client):
    """Test _is_reasoning_model correctly classifies known models."""
    config = OpenAIConfig(model="gpt-4.1")
    llm = OpenAILLM(config)

    # Reasoning models — should return True
    assert llm._is_reasoning_model("o1") is True
    assert llm._is_reasoning_model("o3-mini") is True
    assert llm._is_reasoning_model("o3") is True
    assert llm._is_reasoning_model("gpt-5") is True
    assert llm._is_reasoning_model("o1-preview") is True
    assert llm._is_reasoning_model("o1-2024-12-17") is True
    assert llm._is_reasoning_model("openai/o3-mini") is True

    # Non-reasoning models — should return False
    assert llm._is_reasoning_model("gpt-5.4-mini") is False
    assert llm._is_reasoning_model("gpt-5.4") is False
    assert llm._is_reasoning_model("gpt-4.1") is False
    assert llm._is_reasoning_model("gpt-4.1-nano-2025-04-14") is False


def test_is_reasoning_model_explicit_override(mock_openai_client):
    """Explicit is_reasoning_model overrides the name-based heuristic both ways.

    See https://github.com/mem0ai/mem0/issues/5296 — deployments with custom or
    versioned names need to opt in/out without relying on string matching.
    None (default) must preserve the existing heuristic.
    """
    # Force True: a name the heuristic would reject is now reasoning.
    config_true = OpenAIConfig(model="gpt-5.4-nano-2026-03-17", is_reasoning_model=True)
    llm_true = OpenAILLM(config_true)
    assert llm_true._is_reasoning_model("gpt-5.4-nano-2026-03-17") is True

    # Force False: an o-series name the heuristic would accept is now standard.
    config_false = OpenAIConfig(model="o3-mini", is_reasoning_model=False)
    llm_false = OpenAILLM(config_false)
    assert llm_false._is_reasoning_model("o3-mini") is False

    # None (default) preserves the existing heuristic.
    config_none = OpenAIConfig(model="gpt-4.1")
    llm_none = OpenAILLM(config_none)
    assert config_none.is_reasoning_model is None
    assert llm_none._is_reasoning_model("o3-mini") is True
    assert llm_none._is_reasoning_model("gpt-5.4-mini") is False


def test_is_reasoning_model_override_generates_correct_params(mock_openai_client):
    """End-to-end: is_reasoning_model=True drops max_tokens/temperature from the actual API call."""
    config = OpenAIConfig(
        model="gpt-5.4-nano-2026-03-17",
        temperature=0.7,
        max_tokens=100,
        is_reasoning_model=True,
    )
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert "max_tokens" not in call_kwargs
    assert "temperature" not in call_kwargs


def test_gpt5_uses_max_completion_tokens(mock_openai_client):
    """gpt-5.x (non-reasoning) must send max_completion_tokens, not max_tokens.

    The GPT-5 family rejects the legacy max_tokens param on Chat Completions and
    requires max_completion_tokens. Regression test for
    https://github.com/mem0ai/mem0/issues/5054
    """
    config = OpenAIConfig(model="gpt-5.4-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert call_kwargs.get("max_completion_tokens") == 100
    assert "max_tokens" not in call_kwargs


def test_gpt4_uses_max_tokens(mock_openai_client):
    """Older models (gpt-4.x) keep using max_tokens — guards against regressions."""
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert call_kwargs.get("max_tokens") == 100
    assert "max_completion_tokens" not in call_kwargs


def test_callback_with_tools(mock_openai_client):
    mock_callback = Mock()
    config = OpenAIConfig(model="gpt-4.1-nano-2025-04-14", response_callback=mock_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test tools"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"param1": {"type": "string"}},
                    "required": ["param1"],
                },
            }
        }
    ]
    
    # Mock tool response
    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "Tool response"
    mock_tool_call = Mock()
    mock_tool_call.function.name = "test_tool"
    mock_tool_call.function.arguments = '{"param1": "value1"}'
    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    llm.generate_response(messages, tools=tools)
    
    # Verify callback called with tool response
    mock_callback.assert_called_once()
    # Check that tool_calls exists in the message
    assert hasattr(mock_callback.call_args[0][1].choices[0].message, 'tool_calls')


def test_openai_llm_preserves_proxies_from_base_config(mock_openai_client):
    config = BaseLlmConfig(
        model="gpt-4.1-nano-2025-04-14",
        api_key="api_key",
        http_client_proxies="http://proxy.local:8080",
    )
    llm = OpenAILLM(config)
    assert llm.config.http_client_proxies == "http://proxy.local:8080"
    assert isinstance(llm.config.http_client, httpx.Client)


def _openrouter_client_factory(captured_requests):
    """Build a real `OpenAI` client wired to a mock transport.

    A real client (not a Mock) is what makes this meaningful: the SDK's own
    required-argument validation runs, so a parameter the SDK does not know
    fails here exactly as it would against the live API. No network and no
    API key are involved.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(
            200,
            json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 0,
                "model": "openai/gpt-4o-mini",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            },
        )

    def factory(*args, **kwargs):
        kwargs.pop("api_key", None)
        kwargs.pop("base_url", None)
        return OpenAI(
            api_key="sk-or-test",
            base_url="https://openrouter.ai/api/v1",
            http_client=httpx.Client(transport=httpx.MockTransport(handler)),
        )

    return factory


def test_openrouter_models_fallback_reaches_request_body(monkeypatch):
    """`models`/`route` are OpenRouter-only fields with no OpenAI SDK parameter.

    They have to travel in `extra_body`, and `model` has to stay set, otherwise
    `create()` raises before any request is built. Per OpenRouter's own docs
    (`/docs/guides/routing/model-fallbacks`, "Using with the OpenAI SDK"), the
    first entry of `models` is tried first and the array is the fallback chain.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(
        models=["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"],
        route="fallback",
    )
    llm = OpenAILLM(config)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    assert len(captured) == 1
    body = json.loads(captured[0].content)
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["models"] == ["openai/gpt-4o-mini", "anthropic/claude-3.5-haiku"]
    assert body["route"] == "fallback"


def test_openrouter_without_models_sends_no_fallback_fields(monkeypatch):
    """Without `models` the request must stay a plain OpenAI-shaped call."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(model="openai/gpt-4o-mini")
    llm = OpenAILLM(config)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    body = json.loads(captured[0].content)
    assert body["model"] == "openai/gpt-4o-mini"
    assert "models" not in body
    assert "route" not in body


def test_openrouter_site_url_stays_in_http_headers(monkeypatch):
    """`extra_headers` is an SDK kwarg that sets HTTP headers.

    It must not be folded into `extra_body`, where it would become a JSON field.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(
        models=["openai/gpt-4o-mini"],
        site_url="https://example.test",
        app_name="mem0-test",
    )
    llm = OpenAILLM(config)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    request = captured[0]
    assert request.headers["HTTP-Referer"] == "https://example.test"
    assert request.headers["X-Title"] == "mem0-test"
    body = json.loads(request.content)
    assert "extra_headers" not in body
    assert body["models"] == ["openai/gpt-4o-mini"]


def test_openrouter_resolves_model_before_filtering_params(monkeypatch):
    """The model the request carries must be the model params are derived from.

    `_get_supported_params` classifies `config.model` to decide whether to send
    `temperature`/`top_p`/`max_tokens`. If the effective model is only applied at
    request time, the params are chosen for a different model than the one sent —
    here an `o3-mini` request would carry the non-reasoning parameters derived
    from the `gpt-5-mini` default.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(models=["openai/o3-mini", "openai/gpt-4o-mini"])
    llm = OpenAILLM(config)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    body = json.loads(captured[0].content)
    assert body["model"] == "openai/o3-mini"
    # o3-mini is classified as a reasoning model, so the sampling parameters
    # and the token-limit fields are all dropped.
    assert "temperature" not in body
    assert "top_p" not in body
    assert "max_tokens" not in body
    assert "max_completion_tokens" not in body


def test_openrouter_explicit_model_wins_over_models_list(monkeypatch):
    """`model` is the primary and `models` the fallbacks, per OpenRouter.

    An explicitly configured `model` must not be overwritten by `models[0]`.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(model="openai/gpt-4o-mini", models=["openai/gpt-4o", "anthropic/claude-3.5-haiku"])
    llm = OpenAILLM(config)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    body = json.loads(captured[0].content)
    assert body["model"] == "openai/gpt-4o-mini"
    assert body["models"] == ["openai/gpt-4o", "anthropic/claude-3.5-haiku"]


def test_openrouter_merges_caller_extra_body(monkeypatch):
    """A caller-supplied `extra_body` must survive the OpenRouter fields.

    Callers pass routing preferences that way; replacing the dict would drop
    them without any error.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(models=["openai/gpt-4o-mini"])
    llm = OpenAILLM(config)
    assert (
        llm.generate_response(
            [{"role": "user", "content": "ping"}],
            extra_body={"provider": {"sort": "price"}},
        )
        == "pong"
    )

    body = json.loads(captured[0].content)
    assert body["provider"] == {"sort": "price"}
    assert body["models"] == ["openai/gpt-4o-mini"]
    assert body["route"] == "fallback"


def test_openrouter_merges_caller_extra_body_on_reasoning_path(monkeypatch):
    """The merge must work for reasoning models too.

    `_get_supported_params` rebuilds `params` from scratch for reasoning models
    and never copies `**kwargs` into it, so reading the caller's value out of
    `params` would silently find nothing on that path.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(models=["openai/o3-mini", "openai/gpt-4o-mini"])
    llm = OpenAILLM(config)
    assert (
        llm.generate_response(
            [{"role": "user", "content": "ping"}],
            extra_body={"provider": {"sort": "price"}},
        )
        == "pong"
    )

    body = json.loads(captured[0].content)
    assert body["model"] == "openai/o3-mini"
    assert body["provider"] == {"sort": "price"}
    assert body["models"] == ["openai/o3-mini", "openai/gpt-4o-mini"]


def test_openrouter_merges_caller_extra_headers(monkeypatch):
    """Caller headers survive alongside the attribution headers from config."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(
        models=["openai/gpt-4o-mini"],
        site_url="https://example.test",
        app_name="mem0-test",
    )
    llm = OpenAILLM(config)
    assert (
        llm.generate_response(
            [{"role": "user", "content": "ping"}],
            extra_headers={"X-Caller": "keep-me"},
        )
        == "pong"
    )

    request = captured[0]
    assert request.headers["HTTP-Referer"] == "https://example.test"
    assert request.headers["X-Title"] == "mem0-test"
    assert request.headers["X-Caller"] == "keep-me"


def test_openrouter_decision_is_fixed_at_construction(monkeypatch):
    """The client and the request shape must not disagree.

    The OpenRouter branch is decided when the client is built; re-reading the
    environment on every call would let a later `unset` drop a configured
    fallback chain, or attach OpenRouter-only fields to a plain OpenAI client.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    llm = OpenAILLM(OpenAIConfig(models=["openai/gpt-4o-mini"]))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert llm.generate_response([{"role": "user", "content": "ping"}]) == "pong"

    body = json.loads(captured[0].content)
    assert body["models"] == ["openai/gpt-4o-mini"]
    assert body["route"] == "fallback"


def test_openrouter_keeps_caller_extra_body_without_models(monkeypatch):
    """Caller `extra_body` survives even with nothing OpenRouter-specific set.

    `_get_supported_params` drops `**kwargs` for reasoning models, so restoring
    the caller's value cannot be conditional on `models` being configured.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    llm = OpenAILLM(OpenAIConfig(model="openai/o3-mini"))
    assert (
        llm.generate_response(
            [{"role": "user", "content": "ping"}],
            extra_body={"provider": {"sort": "price"}},
        )
        == "pong"
    )

    body = json.loads(captured[0].content)
    assert body["model"] == "openai/o3-mini"
    assert body["provider"] == {"sort": "price"}
    assert "models" not in body


def test_openrouter_keeps_caller_extra_headers_with_partial_attribution(monkeypatch):
    """Caller headers survive when only one attribution field is configured."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    llm = OpenAILLM(OpenAIConfig(model="openai/o3-mini", site_url="https://example.test"))
    assert (
        llm.generate_response(
            [{"role": "user", "content": "ping"}],
            extra_headers={"X-Trace": "1"},
        )
        == "pong"
    )

    request = captured[0]
    assert request.headers["X-Trace"] == "1"
    # `app_name` is unset, so no attribution headers are configured at all.
    assert "x-title" not in request.headers


def test_openrouter_does_not_mutate_caller_config(monkeypatch):
    """Resolving the primary must not write back into the caller's config.

    `LLMBase` keeps the config object it was handed, so a config reused for a
    second client built without `OPENROUTER_API_KEY` would otherwise carry the
    OpenRouter primary and send it to the OpenAI endpoint.
    """
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-test")
    captured = []
    monkeypatch.setattr("mem0.llms.openai.OpenAI", _openrouter_client_factory(captured))

    config = OpenAIConfig(models=["openai/o3-mini", "openai/gpt-4o-mini"])
    llm = OpenAILLM(config)

    assert llm.config.model == "openai/o3-mini"
    assert config.model is None
    assert llm.config is not config
