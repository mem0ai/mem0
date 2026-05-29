import json
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.xai import XAILLM
from mem0.utils.factory import LlmFactory


@pytest.fixture
def mock_xai_client():
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_factory_construction_with_base_config_does_not_raise():
    """Bug 1 (#5189): the factory wires xai with a plain BaseLlmConfig that has
    no `xai_base_url` attribute. Construction must not raise AttributeError and
    must fall back to the default x.ai base URL."""
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        llm = LlmFactory.create("xai", {"model": "grok-2-latest", "api_key": "sk-test"})
        assert isinstance(llm, XAILLM)
        # default base url forwarded to the OpenAI-compatible client
        assert mock_openai.call_args.kwargs["base_url"] == "https://api.x.ai/v1"


def test_generate_response_without_tools(mock_xai_client):
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="sk-test")
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi there"))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    result = llm.generate_response(messages)

    create_kwargs = mock_xai_client.chat.completions.create.call_args[1]
    assert "tools" not in create_kwargs
    assert "tool_choice" not in create_kwargs
    assert result == "Hi there"


def test_generate_response_forwards_tools(mock_xai_client):
    """Bug 2 (#5189): tools and tool_choice must be forwarded to the client."""
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="sk-test")
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "Remember I like tennis"}]
    tools = [{"type": "function", "function": {"name": "add_memory", "parameters": {}}}]

    mock_message = Mock(content=None)
    mock_message.tool_calls = [
        Mock(function=Mock(name="add_memory", arguments='{"data": "likes tennis"}'))
    ]
    # `name` is special on Mock construction; set it explicitly.
    mock_message.tool_calls[0].function.name = "add_memory"
    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_xai_client.chat.completions.create.return_value = mock_response

    result = llm.generate_response(messages, tools=tools, tool_choice="auto")

    create_kwargs = mock_xai_client.chat.completions.create.call_args[1]
    assert create_kwargs["tools"] == tools
    assert create_kwargs["tool_choice"] == "auto"

    # Bug 3 (#5189): tool-call payload must be parsed, not dropped.
    assert isinstance(result, dict)
    assert result["content"] is None
    assert result["tool_calls"] == [{"name": "add_memory", "arguments": {"data": "likes tennis"}}]


def test_generate_response_with_tools_but_no_tool_calls(mock_xai_client):
    """When tools are supplied but the model returns plain content, the parsed
    response should still be the structured dict with an empty tool_calls list."""
    config = BaseLlmConfig(model="grok-2-latest", api_key="sk-test")
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]
    tools = [{"type": "function", "function": {"name": "noop", "parameters": {}}}]

    mock_message = Mock(content="just text")
    mock_message.tool_calls = []
    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_xai_client.chat.completions.create.return_value = mock_response

    result = llm.generate_response(messages, tools=tools)

    assert result == {"content": "just text", "tool_calls": []}
