from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.cometapi import CometAPIConfig
from mem0.llms.cometapi import CometAPILLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.cometapi.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_init_with_config():
    config = BaseLlmConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = CometAPILLM(config)
    assert llm.config.model == "gpt-4o-mini"
    assert llm.config.temperature == 0.7
    assert llm.config.max_tokens == 100
    assert llm.config.top_p == 1.0


def test_init_with_cometapi_config():
    config = CometAPIConfig(
        model="gpt-5-mini", temperature=0.5, max_tokens=200, cometapi_base_url="https://api.cometapi.com/v1/"
    )
    with patch("mem0.llms.cometapi.OpenAI") as mock_openai:
        llm = CometAPILLM(config)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://api.cometapi.com/v1/"
        assert llm.config.model == "gpt-5-mini"


def test_init_without_config(mock_openai_client):
    llm = CometAPILLM()
    assert llm.config.model == "gpt-4o-mini"  # Default model


def test_init_with_env_api_key(mock_openai_client, monkeypatch):
    monkeypatch.setenv("COMETAPI_KEY", "test-api-key")
    CometAPILLM()
    # Check that OpenAI client was initialized with the API key
    assert mock_openai_client is not None


def test_generate_response_without_tools(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = CometAPILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o-mini", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = CometAPILLM(config)
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
        model="gpt-4o-mini",
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


def test_generate_response_with_response_format(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = CometAPILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Return JSON with name and age."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"name": "John", "age": 30}'))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o-mini",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )
    assert response == '{"name": "John", "age": 30}'


def test_parse_response_without_tools(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini")
    llm = CometAPILLM(config)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Simple response"))]

    result = llm._parse_response(mock_response, tools=None)
    assert result == "Simple response"


def test_parse_response_with_tools_no_tool_calls(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini")
    llm = CometAPILLM(config)

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "No tool calls needed"
    mock_message.tool_calls = None
    mock_response.choices = [Mock(message=mock_message)]

    tools = [{"type": "function", "function": {"name": "test_function"}}]
    result = llm._parse_response(mock_response, tools=tools)

    assert result["content"] == "No tool calls needed"
    assert result["tool_calls"] == []


def test_parse_response_with_multiple_tool_calls(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o-mini")
    llm = CometAPILLM(config)

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "Using multiple tools"

    mock_tool_call_1 = Mock()
    mock_tool_call_1.function.name = "tool_one"
    mock_tool_call_1.function.arguments = '{"param": "value1"}'

    mock_tool_call_2 = Mock()
    mock_tool_call_2.function.name = "tool_two"
    mock_tool_call_2.function.arguments = '{"param": "value2"}'

    mock_message.tool_calls = [mock_tool_call_1, mock_tool_call_2]
    mock_response.choices = [Mock(message=mock_message)]

    tools = [{"type": "function"}]
    result = llm._parse_response(mock_response, tools=tools)

    assert result["content"] == "Using multiple tools"
    assert len(result["tool_calls"]) == 2
    assert result["tool_calls"][0]["name"] == "tool_one"
    assert result["tool_calls"][0]["arguments"] == {"param": "value1"}
    assert result["tool_calls"][1]["name"] == "tool_two"
    assert result["tool_calls"][1]["arguments"] == {"param": "value2"}
