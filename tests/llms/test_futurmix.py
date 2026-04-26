import json
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.futurmix import FuturMixConfig
from mem0.llms.futurmix import FuturMixLLM


@pytest.fixture
def mock_futurmix_client():
    with patch("mem0.llms.futurmix.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_futurmix_client):
    config = BaseLlmConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = FuturMixLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_futurmix_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_futurmix_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_futurmix_client):
    config = BaseLlmConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = FuturMixLLM(config)
    messages = [
        {"role": "user", "content": "What's the weather in SF?"},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the weather for a location",
                "parameters": {
                    "type": "object",
                    "properties": {"location": {"type": "string"}},
                    "required": ["location"],
                },
            },
        }
    ]

    mock_tool_call = Mock()
    mock_tool_call.function.name = "get_weather"
    mock_tool_call.function.arguments = json.dumps({"location": "San Francisco"})

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=None, tool_calls=[mock_tool_call]))]
    mock_futurmix_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools, tool_choice="auto")

    mock_futurmix_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools, tool_choice="auto"
    )
    assert response["tool_calls"][0]["name"] == "get_weather"
    assert response["tool_calls"][0]["arguments"] == {"location": "San Francisco"}


def test_custom_base_url_via_config():
    with patch("mem0.llms.futurmix.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        config = FuturMixConfig(model="gpt-4o", api_key="test-key", futurmix_base_url="https://custom.example.com/v1")
        llm = FuturMixLLM(config)

        mock_openai.assert_called_once_with(api_key="test-key", base_url="https://custom.example.com/v1")


def test_default_base_url():
    with patch("mem0.llms.futurmix.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        config = FuturMixConfig(model="gpt-4o", api_key="test-key")
        llm = FuturMixLLM(config)

        mock_openai.assert_called_once_with(api_key="test-key", base_url="https://futurmix.ai/v1")


def test_default_model():
    with patch("mem0.llms.futurmix.OpenAI") as mock_openai:
        mock_openai.return_value = Mock()
        config = FuturMixConfig(api_key="test-key")
        llm = FuturMixLLM(config)

        assert llm.config.model == "gpt-4o"
