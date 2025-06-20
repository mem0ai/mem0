from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_client():
    with patch("mem0.llms.gemini.genai.Client") as mock_client:
        yield mock_client.return_value


def test_generate_response_without_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_part = Mock(text="I'm doing well, thank you for asking!")
    mock_content = Mock(parts=[mock_part])
    mock_message = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_message])
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    # Check that generate_content was called with the correct parameters
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args
    
    # Verify model parameter
    assert call_args[1]['model'] == "gemini-1.5-flash-latest"
    
    # Verify contents parameter - check that system prompt and user message are properly formatted
    contents = call_args[1]['contents']
    assert len(contents) == 2
    assert contents[0].role == "user"  # System prompts are sent as user role with special prefix
    assert "THIS IS A SYSTEM PROMPT" in contents[0].parts[0].text
    assert "You are a helpful assistant" in contents[0].parts[0].text
    assert contents[1].role == "user"
    assert contents[1].parts[0].text == "Hello, how are you?"
    
    # Verify config parameters
    config = call_args[1]['config']
    assert config.temperature == 0.7
    assert config.max_output_tokens == 100
    assert config.top_p == 1.0
    assert config.tools is None
    
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

    mock_part = Mock()
    mock_part.function_call = mock_tool_call
    mock_part.text = "I've added the memory for you."

    mock_content = Mock()
    mock_content.parts = [mock_part]

    mock_message = Mock()
    mock_message.content = mock_content

    mock_response = Mock(candidates=[mock_message])
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Check that generate_content was called with the correct parameters
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args
    
    # Verify model parameter
    assert call_args[1]['model'] == "gemini-1.5-flash-latest"
    
    # Verify contents parameter
    contents = call_args[1]['contents']
    assert len(contents) == 2
    assert contents[0].role == "user"  # System prompts are sent as user role with special prefix
    assert "THIS IS A SYSTEM PROMPT" in contents[0].parts[0].text
    assert "You are a helpful assistant" in contents[0].parts[0].text
    assert contents[1].role == "user"
    assert contents[1].parts[0].text == "Add a new memory: Today is a sunny day."
    
    # Verify config parameters
    config = call_args[1]['config']
    assert config.temperature == 0.7
    assert config.max_output_tokens == 100
    assert config.top_p == 1.0
    
    # Verify tool_config
    assert config.tool_config is not None
    assert config.tool_config.function_calling_config.mode == "AUTO"
    
    # Verify response processing
    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
