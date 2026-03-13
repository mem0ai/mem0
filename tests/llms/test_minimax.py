import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.minimax import MiniMaxConfig
from mem0.llms.minimax import MiniMaxLLM


@pytest.fixture
def mock_minimax_client():
    with patch("mem0.llms.minimax.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_minimax_llm_base_url():
    # case1: default config with MiniMax official base url
    config = BaseLlmConfig(model="MiniMax-M1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = MiniMaxLLM(config)
    assert str(llm.client.base_url).rstrip("/") == "https://api.minimax.io/v1"

    # case2: with env variable MINIMAX_API_BASE
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["MINIMAX_API_BASE"] = provider_base_url
    config = MiniMaxConfig(model="MiniMax-M1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = MiniMaxLLM(config)
    assert str(llm.client.base_url) == provider_base_url

    # case3: with config.minimax_base_url
    config_base_url = "https://api.config.com/v1/"
    config = MiniMaxConfig(
        model="MiniMax-M1",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        minimax_base_url=config_base_url,
    )
    llm = MiniMaxLLM(config)
    assert str(llm.client.base_url) == config_base_url

    # cleanup
    del os.environ["MINIMAX_API_BASE"]


def test_generate_response_without_tools(mock_minimax_client):
    config = BaseLlmConfig(model="MiniMax-M1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MiniMaxLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_minimax_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_minimax_client.chat.completions.create.assert_called_once_with(
        model="MiniMax-M1", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_minimax_client):
    config = BaseLlmConfig(model="MiniMax-M1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MiniMaxLLM(config)
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
    mock_minimax_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_minimax_client.chat.completions.create.assert_called_once_with(
        model="MiniMax-M1",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        tools=tools,
        tool_choice="auto",
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
