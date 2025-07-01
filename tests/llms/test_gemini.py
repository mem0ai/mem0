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

    mock_part = Mock()
    mock_part.text = "I'm doing well, thank you for asking!"

    mock_content = Mock()
    mock_content.parts = [mock_part]

    mock_candidate = Mock()
    mock_candidate.content = mock_content

    mock_response = Mock()
    mock_response.candidates = [mock_candidate]

    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    # Check that the correct method was called
    mock_gemini_client.models.generate_content.assert_called_once()
    
    # Get the actual call arguments
    call_args = mock_gemini_client.models.generate_content.call_args
    
    # Verify the model parameter
    assert call_args.kwargs["model"] == "gemini-2.0-flash-latest"
    
    # Verify the contents format - should be list of Content objects
    contents = call_args.kwargs["contents"]
    assert len(contents) == 1  # Only user message, system is in config
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Hello, how are you?"
    
    # Verify the config
    config_obj = call_args.kwargs["config"]
    assert config_obj.temperature == 0.7
    assert config_obj.max_output_tokens == 100
    assert config_obj.top_p == 1.0
    assert config_obj.system_instruction == "You are a helpful assistant."
    assert config_obj.tools is None
    
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

    # Create a proper mock for the function call arguments
    mock_args = {"data": "Today is a sunny day."}
    
    mock_tool_call = Mock()
    mock_tool_call.name = "add_memory"
    mock_tool_call.args = mock_args

    mock_part_text = Mock()
    mock_part_text.text = "I've added the memory for you."
    mock_part_text.function_call = None  # Ensure this part doesn't have function_call
    
    mock_part_function = Mock()
    mock_part_function.function_call = mock_tool_call
    mock_part_function.text = None

    mock_content = Mock()
    mock_content.parts = [mock_part_text, mock_part_function]

    mock_candidate = Mock()
    mock_candidate.content = mock_content

    mock_response = Mock(candidates=[mock_candidate])
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Check that the correct method was called
    mock_gemini_client.models.generate_content.assert_called_once()
    
    # Get the actual call arguments
    call_args = mock_gemini_client.models.generate_content.call_args
    
    # Verify the model parameter
    assert call_args.kwargs["model"] == "gemini-1.5-flash-latest"
    
    # Verify the contents format
    contents = call_args.kwargs["contents"]
    assert len(contents) == 1  # Only user message, system is in config
    assert contents[0].role == "user"
    assert contents[0].parts[0].text == "Add a new memory: Today is a sunny day."
    
    # Verify the config
    config_obj = call_args.kwargs["config"]
    assert config_obj.temperature == 0.7
    assert config_obj.max_output_tokens == 100
    assert config_obj.top_p == 1.0
    assert config_obj.system_instruction == "You are a helpful assistant."
    
    # Verify tools are present
    assert config_obj.tools is not None
    assert len(config_obj.tools) == 1
    assert len(config_obj.tools[0].function_declarations) == 1
    assert config_obj.tools[0].function_declarations[0].name == "add_memory"
    
    # Verify tool config
    assert config_obj.tool_config is not None
    assert config_obj.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.AUTO

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
