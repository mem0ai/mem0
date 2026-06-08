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


def test_xai_llm_default_base_url():
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        XAILLM(config)

    mock_openai.assert_called_once_with(api_key="api_key", base_url="https://api.x.ai/v1")


def test_xai_llm_env_base_url():
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["XAI_API_BASE"] = provider_base_url
    try:
        config = XAIConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
        with patch("mem0.llms.xai.OpenAI") as mock_openai:
            XAILLM(config)

        mock_openai.assert_called_once_with(api_key="api_key", base_url=provider_base_url)
    finally:
        os.environ.pop("XAI_API_BASE", None)


def test_xai_llm_config_base_url():
    config_base_url = "https://api.config.com/v1/"
    config = XAIConfig(
        model="grok-2-latest",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        xai_base_url=config_base_url,
    )
    with patch("mem0.llms.xai.OpenAI") as mock_openai:
        XAILLM(config)

    mock_openai.assert_called_once_with(api_key="api_key", base_url=config_base_url)


def test_factory_creates_xai_llm(mock_xai_client):
    llm = LlmFactory.create("xai", {"model": "grok-2-latest", "api_key": "test-key"})
    assert isinstance(llm, XAILLM)
    assert llm.config.model == "grok-2-latest"


def test_factory_accepts_xai_base_url(mock_xai_client):
    llm = LlmFactory.create(
        "xai",
        {"model": "grok-2-latest", "api_key": "test-key", "xai_base_url": "https://custom.x.ai/v1"},
    )

    assert llm.config.xai_base_url == "https://custom.x.ai/v1"
    mock_xai_client.chat.completions.create.assert_not_called()


def test_generate_response_without_tools(mock_xai_client):
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
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
        model="grok-2-latest", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_xai_client):
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
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
    mock_message.content = None

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

    assert response["content"] is None
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_with_response_format(mock_xai_client):
    config = BaseLlmConfig(model="grok-2-latest", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = XAILLM(config)
    messages = [{"role": "user", "content": "Return JSON."}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
    mock_xai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format=response_format)

    mock_xai_client.chat.completions.create.assert_called_once_with(
        model="grok-2-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )
