from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms import litellm


@pytest.fixture
def mock_litellm():
    with patch("mem0.llms.litellm.litellm") as mock_litellm:
        yield mock_litellm


def test_generate_response_with_unsupported_model(mock_litellm):
    config = BaseLlmConfig(model="unsupported-model", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_litellm.supports_function_calling.return_value = False

    with pytest.raises(ValueError, match="Model 'unsupported-model' in litellm does not support function calling."):
        llm.generate_response(messages)


def test_generate_response_without_tools(mock_litellm):
    config = BaseLlmConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_litellm):
    config = BaseLlmConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
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
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages, tools=tools)

    mock_litellm.completion.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1, tools=tools, tool_choice="auto"
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_with_model_as_dict(mock_litellm):
    """Test that model can be specified as a dict with name and additional parameters."""
    config = BaseLlmConfig(
        model={"name": "gemini/gemini-2.5-flash-preview-04-17", "reasoning_effort": "low"},
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hello! How can I help you?"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gemini/gemini-2.5-flash-preview-04-17",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        reasoning_effort="low",
    )
    assert response == "Hello! How can I help you?"


def test_generate_response_with_reasoning_effort_high(mock_litellm):
    """Test reasoning_effort parameter with 'high' value for Gemini models."""
    config = BaseLlmConfig(
        model={
            "name": "gemini/gemini-2.5-flash-preview-04-17",
            "reasoning_effort": "high",
        },
        temperature=0.2,
        max_tokens=4000,
        top_p=0.9,
    )
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Solve this complex math problem"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Let me think about this..."))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gemini/gemini-2.5-flash-preview-04-17",
        messages=messages,
        temperature=0.2,
        max_tokens=4000,
        top_p=0.9,
        reasoning_effort="high",
    )
    assert response == "Let me think about this..."


def test_generate_response_with_multiple_model_params(mock_litellm):
    """Test multiple model-specific parameters passed via dict."""
    config = BaseLlmConfig(
        model={
            "name": "gemini/gemini-2.5-flash-preview-04-17",
            "reasoning_effort": "medium",
            "frequency_penalty": 0.5,
            "seed": 42,
        },
        temperature=0.5,
        max_tokens=2000,
        top_p=0.95,
    )
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Generate some text"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Generated text here."))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gemini/gemini-2.5-flash-preview-04-17",
        messages=messages,
        temperature=0.5,
        max_tokens=2000,
        top_p=0.95,
        reasoning_effort="medium",
        frequency_penalty=0.5,
        seed=42,
    )
    assert response == "Generated text here."


def test_get_model_name_with_string(mock_litellm):
    """Test _get_model_name returns correct name when model is a string."""
    config = BaseLlmConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = litellm.LiteLLM(config)

    assert llm._get_model_name() == "gpt-4.1-nano-2025-04-14"


def test_get_model_name_with_dict(mock_litellm):
    """Test _get_model_name returns correct name when model is a dict."""
    config = BaseLlmConfig(
        model={"name": "gemini/gemini-2.5-flash-preview-04-17", "reasoning_effort": "low"},
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    llm = litellm.LiteLLM(config)

    assert llm._get_model_name() == "gemini/gemini-2.5-flash-preview-04-17"


def test_init_with_dict_model_without_name(mock_litellm):
    """Test that default model name is set when dict model doesn't have 'name' key."""
    config = BaseLlmConfig(
        model={"reasoning_effort": "low"},
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    llm = litellm.LiteLLM(config)

    assert llm._get_model_name() == "gpt-4.1-nano-2025-04-14"
    assert llm.config.model["reasoning_effort"] == "low"


def test_generate_response_with_unsupported_model_as_dict(mock_litellm):
    """Test error handling when model (as dict) doesn't support function calling."""
    config = BaseLlmConfig(
        model={"name": "unsupported-model", "reasoning_effort": "low"},
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_litellm.supports_function_calling.return_value = False

    with pytest.raises(ValueError, match="Model 'unsupported-model' in litellm does not support function calling."):
        llm.generate_response(messages)
