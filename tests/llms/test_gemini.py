from unittest.mock import Mock, patch

import pytest
from google.genai import types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_client():
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-2.0-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_part = Mock(text="I'm doing well, thank you for asking!")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])

    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    # Check the actual call - system instruction is now in config
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args

    # Verify model and contents
    assert call_args.kwargs["model"] == "gemini-2.0-flash-latest"
    assert len(call_args.kwargs["contents"]) == 1  # Only user message

    # Verify config has system instruction
    config_arg = call_args.kwargs["config"]
    assert config_arg.system_instruction == "You are a helpful assistant."
    assert config_arg.temperature == 0.7
    assert config_arg.max_output_tokens == 100
    assert config_arg.top_p == 1.0

    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
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

    mock_tool_call = Mock()
    mock_tool_call.name = "add_memory"
    mock_tool_call.args = {"data": "Today is a sunny day."}

    # Create mock parts with both text and function_call
    mock_text_part = Mock()
    mock_text_part.text = "I've added the memory for you."
    mock_text_part.function_call = None

    mock_func_part = Mock()
    mock_func_part.text = None
    mock_func_part.function_call = mock_tool_call

    mock_content = Mock()
    mock_content.parts = [mock_text_part, mock_func_part]

    mock_candidate = Mock()
    mock_candidate.content = mock_content

    mock_response = Mock(candidates=[mock_candidate])
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Check the actual call
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args

    # Verify model and contents
    assert call_args.kwargs["model"] == "gemini-1.5-flash-latest"
    assert len(call_args.kwargs["contents"]) == 1  # Only user message

    # Verify config has system instruction and tools
    config_arg = call_args.kwargs["config"]
    assert config_arg.system_instruction == "You are a helpful assistant."
    assert config_arg.temperature == 0.7
    assert config_arg.max_output_tokens == 100
    assert config_arg.top_p == 1.0
    assert len(config_arg.tools) == 1
    assert config_arg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.AUTO

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
