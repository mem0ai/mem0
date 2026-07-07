import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.xai import XAIConfig
from mem0.llms.xai import XAILLM
from mem0.utils.factory import LlmFactory


@pytest.fixture
def mock_xai_client():
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_xai_llm_base_url():
    # case1: default
    config = XAIConfig(model="grok-2-latest", api_key="api_key")
    llm = XAILLM(config)
    assert str(llm.client.base_url) == "https://api.x.ai/v1/"

    # case2: XAI_API_BASE env var
    os.environ["XAI_API_BASE"] = "https://api.provider.com/v1"
    config = XAIConfig(model="grok-2-latest", api_key="api_key")
    llm = XAILLM(config)
    assert str(llm.client.base_url) == "https://api.provider.com/v1/"

    # case3: config.xai_base_url wins over env
    config = XAIConfig(
        model="grok-2-latest",
        api_key="api_key",
        xai_base_url="https://api.config.com/v1",
    )
    llm = XAILLM(config)
    assert str(llm.client.base_url) == "https://api.config.com/v1/"


def test_xai_accepts_base_llm_config():
    # Used to AttributeError on self.config.xai_base_url because the factory
    # wired XAI with plain BaseLlmConfig.
    llm = XAILLM(BaseLlmConfig(model="grok-2-latest", api_key="k"))
    assert isinstance(llm.config, XAIConfig)
    assert llm.config.xai_base_url is None


def test_generate_response_without_tools(mock_xai_client):
    config = XAIConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = XAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_xai_client.chat.completions.create.assert_called_once_with(
        model="grok-2-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_xai_client):
    config = XAIConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = XAILLM(config)
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
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_xai_client.chat.completions.create.assert_called_once_with(
        model="grok-2-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        tools=tools,
        tool_choice="auto",
    )

    assert response["content"] == "I've added the memory for you."
    assert response["tool_calls"] == [{"name": "add_memory", "arguments": {"data": "Today is a sunny day."}}]


def test_empty_tools_list_not_forwarded(mock_xai_client):
    # tools=[] would otherwise get rejected by some OpenAI-compatible backends
    config = XAIConfig(model="grok-2-latest", api_key="api_key")
    llm = XAILLM(config)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="hello"))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response([{"role": "user", "content": "hi"}], tools=[])

    call_kwargs = mock_xai_client.chat.completions.create.call_args.kwargs
    assert "tools" not in call_kwargs
    assert "tool_choice" not in call_kwargs
    assert response == "hello"


def test_tools_requested_but_model_returns_no_calls(mock_xai_client):
    # Model can decline to call any tool even when offered
    config = XAIConfig(model="grok-2-latest", api_key="api_key")
    llm = XAILLM(config)
    tools = [{"type": "function", "function": {"name": "f", "parameters": {"type": "object", "properties": {}}}}]

    mock_message = Mock(content="just a chat reply")
    mock_message.tool_calls = None
    mock_xai_client.chat.completions.create.return_value = Mock(choices=[Mock(message=mock_message)])

    response = llm.generate_response([{"role": "user", "content": "x"}], tools=tools)
    assert response == {"content": "just a chat reply", "tool_calls": []}


def test_generate_response_with_response_format(mock_xai_client):
    config = XAIConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = XAILLM(config)
    messages = [
        {"role": "system", "content": "You are a memory extraction assistant."},
        {"role": "user", "content": "I like hiking on weekends."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"facts": ["User likes hiking on weekends"]}'))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    mock_xai_client.chat.completions.create.assert_called_once_with(
        model="grok-2-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )
    assert response == '{"facts": ["User likes hiking on weekends"]}'


def test_generate_response_without_response_format(mock_xai_client):
    config = XAIConfig(model="grok-2-latest", api_key="api_key")
    llm = XAILLM(config)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="hi"))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    llm.generate_response([{"role": "user", "content": "hi"}])

    call_kwargs = mock_xai_client.chat.completions.create.call_args.kwargs
    assert "response_format" not in call_kwargs


def test_factory_creates_xai_from_dict():
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        llm = LlmFactory.create(
            "xai",
            {"model": "grok-2-latest", "api_key": "k", "xai_base_url": "https://example.com/v1"},
        )
    assert isinstance(llm, XAILLM)
    assert isinstance(llm.config, XAIConfig)
    assert llm.config.xai_base_url == "https://example.com/v1"


def test_factory_creates_xai_from_base_config():
    # Legacy callers still hand the factory a plain BaseLlmConfig
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        llm = LlmFactory.create("xai", BaseLlmConfig(model="grok-2-latest", api_key="k"))
    assert isinstance(llm.config, XAIConfig)
