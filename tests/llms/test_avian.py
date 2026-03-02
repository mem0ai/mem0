import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.avian import AvianConfig
from mem0.llms.avian import AvianLLM


@pytest.fixture
def mock_avian_client():
    with patch("mem0.llms.avian.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_avian_llm_base_url():
    # case1: default config with avian official base url
    config = BaseLlmConfig(model="deepseek/deepseek-v3.2", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AvianLLM(config)
    assert str(llm.client.base_url).rstrip("/") == "https://api.avian.io/v1"

    # case2: with env variable AVIAN_API_BASE
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["AVIAN_API_BASE"] = provider_base_url
    config = AvianConfig(model="deepseek/deepseek-v3.2", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AvianLLM(config)
    assert str(llm.client.base_url).rstrip("/") == provider_base_url.rstrip("/")

    # case3: with config.avian_base_url
    config_base_url = "https://api.config.com/v1/"
    config = AvianConfig(
        model="deepseek/deepseek-v3.2",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        avian_base_url=config_base_url,
    )
    llm = AvianLLM(config)
    assert str(llm.client.base_url).rstrip("/") == config_base_url.rstrip("/")

    # Cleanup
    del os.environ["AVIAN_API_BASE"]


def test_avian_llm_default_model():
    config = AvianConfig(api_key="api_key")
    llm = AvianLLM(config)
    assert llm.config.model == "deepseek/deepseek-v3.2"


def test_generate_response_without_tools(mock_avian_client):
    config = BaseLlmConfig(model="deepseek/deepseek-v3.2", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AvianLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_avian_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_avian_client.chat.completions.create.assert_called_once_with(
        model="deepseek/deepseek-v3.2", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_avian_client):
    config = BaseLlmConfig(model="deepseek/deepseek-v3.2", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AvianLLM(config)
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
    mock_avian_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_avian_client.chat.completions.create.assert_called_once_with(
        model="deepseek/deepseek-v3.2",
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
