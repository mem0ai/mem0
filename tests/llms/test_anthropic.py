from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.anthropic import AnthropicLLM

MODEL = "claude-3-opus-20240229"
TEMPERATURE = 0.7
MAX_TOKENS = 100
TOP_P = 1.0


@pytest.fixture
def mock_anthropic_client():
    with patch("mem0.llms.anthropic.anthropic.Anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.return_value = mock_client
        yield mock_client


def test_generate_response_basic(mock_anthropic_client):
    """Test basic response generation without special formatting."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text="I'm doing well, thank you for asking!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=messages,
        system="",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_system_message(mock_anthropic_client):
    """Test response generation with a system message."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text="Hello! How can I assist you today?")]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages)

    # System message should be separated from other messages
    expected_messages = [{"role": "user", "content": "Hello!"}]

    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=expected_messages,
        system="You are a helpful assistant.",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    assert response == "Hello! How can I assist you today?"


def test_generate_response_json_format(mock_anthropic_client):
    """Test response generation with JSON formatting request."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Extract facts: Today is sunny and I had coffee."}
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='{"facts": ["Today is sunny", "I had coffee"]}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    expected_messages = [
        {"role": "user", "content": "Extract facts: Today is sunny and I had coffee."}
    ]

    # include prefilled response included in generate_response()
    expected_messages.append(
        {"role": "assistant", "content": "Here is the JSON requested:\n"}
    )
    response = llm.generate_response(
        messages,
        response_format={"type": "json_object"}
    )

    # Check that JSON instruction was added to system message
    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=expected_messages,
        system="You are a helpful assistant.",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    assert response == '{"facts": ["Today is sunny", "I had coffee"]}'


def test_generate_response_json_format_no_system(mock_anthropic_client):
    """Test JSON formatting with no existing system message."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "user", "content": "Extract facts: Today is sunny and I had coffee."},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='{"facts": ["Today is sunny", "I had coffee"]}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(
        messages,
        response_format={"type": "json_object"}
    )

    # add prefilled response included in generate_response()
    messages.append({"role": "assistant", "content": "Here is the JSON requested:\n"})

    # Check that JSON instruction was added as system message
    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=messages,
        system="",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    assert response == '{"facts": ["Today is sunny", "I had coffee"]}'


def test_generate_response_with_tools(mock_anthropic_client):
    """Test response generation with tools configuration."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    messages = [{"role": "user", "content": "What's the weather?"}]
    tools = [
        {
            "name": "get_weather",
            "description": "Get the current weather",
            "input_schema": {
                "type": "object",
                "properties": {
                    "location": {"type": "string"},
                },
                "required": ["location"]
            }
        }
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='{"function": "get_weather", "arguments": {"location": "San Francisco"}}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(
        messages,
        tools=tools,
        tool_choice="auto"
    )

    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=messages,
        system="",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
        tools=tools,
        tool_choice="auto"
    )
    assert response == '{"function": "get_weather", "arguments": {"location": "San Francisco"}}'


def test_generate_response_with_fact_retrieval(mock_anthropic_client):
    """Test response generation with fact retrieval system message and JSON format."""
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AnthropicLLM(config)
    
    # Import here to avoid circular imports in tests
    from mem0.configs.prompts import FACT_RETRIEVAL_PROMPT
    from mem0.memory.utils import get_fact_retrieval_messages
    
    system_msg, user_msg = get_fact_retrieval_messages("I like pizza and pasta.")
    messages = [
        {"role": "system", "content": system_msg},
        {"role": "user", "content": user_msg},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='{"facts": ["User likes pizza", "User likes pasta"]}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(
        messages,
        response_format={"type": "json_object"}
    )

    expected_messages = [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": "Here is the JSON requested:\n"}
    ]

    mock_anthropic_client.messages.create.assert_called_once_with(
        model=MODEL,
        messages=expected_messages,
        system=FACT_RETRIEVAL_PROMPT,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    assert response == '{"facts": ["User likes pizza", "User likes pasta"]}'
