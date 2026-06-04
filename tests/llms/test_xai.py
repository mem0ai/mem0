import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.xai import XAIConfig
from mem0.llms.xai import XAILLM


@pytest.fixture
def mock_xai_client():
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def _normalize_url(url):
    """Strip trailing slash for stable URL comparison."""
    return str(url).rstrip("/")


def test_xai_llm_factory_construction_with_base_config():
    """Regression test for mem0#5189 bug 1: constructing XAILLM via the
    factory (which passes BaseLlmConfig, not XAIConfig) must not raise
    AttributeError on the missing xai_base_url attribute."""
    config = BaseLlmConfig(
        model="grok-2-latest",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
    )
    # This used to raise: AttributeError: 'BaseLlmConfig' object has no attribute 'xai_base_url'
    llm = XAILLM(config)
    assert _normalize_url(llm.client.base_url) == "https://api.x.ai/v1"


def test_xai_llm_base_url():
    # case1: default config with xAI official base url
    config = BaseLlmConfig(
        model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = XAILLM(config)
    assert _normalize_url(llm.client.base_url) == "https://api.x.ai/v1"

    # case2: with env variable XAI_API_BASE
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["XAI_API_BASE"] = provider_base_url
    try:
        config = XAIConfig(
            model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
        )
        llm = XAILLM(config)
        assert _normalize_url(llm.client.base_url) == _normalize_url(provider_base_url)
    finally:
        del os.environ["XAI_API_BASE"]

    # case3: with config.xai_base_url (takes precedence over env)
    config_base_url = "https://api.config.com/v1/"
    config = XAIConfig(
        model="grok-2-latest",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        xai_base_url=config_base_url,
    )
    llm = XAILLM(config)
    assert _normalize_url(llm.client.base_url) == _normalize_url(config_base_url)


def test_xai_llm_dict_config():
    """XAILLM should accept a plain dict config (factory passes dicts)."""
    llm = XAILLM({"model": "grok-2-latest", "api_key": "k"})
    assert _normalize_url(llm.client.base_url) == "https://api.x.ai/v1"
    assert llm.config.model == "grok-2-latest"


def test_xai_llm_none_config_uses_defaults(monkeypatch):
    """XAILLM(None) should fall back to XAIConfig defaults."""
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    llm = XAILLM(None)
    assert llm.config.model == "grok-2-latest"


def test_generate_response_without_tools(mock_xai_client):
    config = BaseLlmConfig(
        model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0
    )
    llm = XAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello."},
    ]
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi there."))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)
    assert response == "Hi there."

    mock_xai_client.chat.completions.create.assert_called_once_with(
        model="grok-2-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )


def test_generate_response_with_tools_forwards_them(mock_xai_client):
    """Regression test for mem0#5189 bug 2: tools and tool_choice must be
    forwarded to chat.completions.create; previously they were silently
    dropped on grok."""
    config = BaseLlmConfig(
        model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0
    )
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "find X"}]
    tools = [
        {
            "type": "function",
            "function": {"name": "search", "parameters": {"type": "object", "properties": {}}},
        }
    ]

    mock_tool_call = Mock()
    mock_tool_call.function.name = "search"
    mock_tool_call.function.arguments = '{"q": "X"}'
    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content=None, tool_calls=[mock_tool_call]))
    ]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Tools must reach the API
    call_kwargs = mock_xai_client.chat.completions.create.call_args.kwargs
    assert "tools" in call_kwargs
    assert call_kwargs["tools"] == tools
    assert call_kwargs["tool_choice"] == "auto"

    # Regression for mem0#5189 bug 3: tool_calls must be present in
    # the parsed response so callers can act on them.
    assert isinstance(response, dict)
    assert response["content"] is None
    assert response["tool_calls"] == [{"name": "search", "arguments": {"q": "X"}}]


def test_generate_response_tools_no_tool_calls(mock_xai_client):
    """When tools are provided but the model replies in plain content,
    tool_calls should be an empty list (no crash on None tool_calls)."""
    config = BaseLlmConfig(model="grok-2-latest")
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "hi"}]
    tools = [{"type": "function", "function": {"name": "search", "parameters": {"type": "object"}}}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="plain reply", tool_calls=None))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)
    assert response == {"content": "plain reply", "tool_calls": []}
