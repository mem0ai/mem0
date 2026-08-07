from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.together import TogetherLLM


@pytest.fixture
def mock_together_client():
    with patch("mem0.llms.together.Together") as mock_together:
        mock_client = Mock()
        mock_together.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_together_client):
    config = BaseLlmConfig(model="mistralai/Mixtral-8x7B-Instruct-v0.1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_together_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    _, kwargs = mock_together_client.chat.completions.create.call_args
    assert kwargs["model"] == "mistralai/Mixtral-8x7B-Instruct-v0.1"
    assert kwargs["messages"] == messages
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 100
    assert kwargs["top_p"] == 1.0
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_together_client):
    config = BaseLlmConfig(model="mistralai/Mixtral-8x7B-Instruct-v0.1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
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
    mock_together_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    _, kwargs = mock_together_client.chat.completions.create.call_args
    assert kwargs["model"] == "mistralai/Mixtral-8x7B-Instruct-v0.1"
    assert kwargs["messages"] == messages
    assert kwargs["temperature"] == 0.7
    assert kwargs["max_tokens"] == 100
    assert kwargs["top_p"] == 1.0
    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_forwards_extra_kwargs(mock_together_client):
    """Per the LLMBase contract, extra provider-specific kwargs must be accepted and
    forwarded to the Together client (matching openai/deepseek/vllm/xai behavior)."""
    config = BaseLlmConfig(model="mistralai/Mixtral-8x7B-Instruct-v0.1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_together_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, frequency_penalty=0.5)

    assert response == "Hi"
    call_kwargs = mock_together_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["frequency_penalty"] == 0.5


def test_generate_response_reasoning_model_omits_temperature(mock_together_client):
    config = BaseLlmConfig(model="o3-mini", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_together_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    _, kwargs = mock_together_client.chat.completions.create.call_args
    assert "temperature" not in kwargs
    assert "top_p" not in kwargs
    assert kwargs["model"] == "o3-mini"
    assert kwargs.get("max_completion_tokens") == 100
    assert "max_tokens" not in kwargs
