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
    config = BaseLlmConfig(model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    # Mock the response structure for the new SDK
    mock_embedding = Mock()
    mock_embedding.values = [0.1, 0.2, 0.3]
    
    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = "I'm doing well, thank you for asking!"
    
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    # Verify the call was made with correct parameters
    mock_gemini_client.models.generate_content.assert_called_once_with(
        model="gemini-1.5-flash-latest",
        contents=[
            types.Content(
                parts=[types.Part(text="Hello, how are you?")],
                role="user"
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=100,
            top_p=1.0,
            system_instruction="You are a helpful assistant."
        )
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
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

    # Mock function call response
    mock_function_call = Mock()
    mock_function_call.name = "add_memory"
    mock_function_call.args = {"data": "Today is a sunny day."}

    # Mock text part
    mock_text_part = Mock()
    mock_text_part.text = "I've added the memory for you."
    mock_text_part.function_call = None

    # Mock function call part
    mock_function_part = Mock()
    mock_function_part.text = None
    mock_function_part.function_call = mock_function_call

    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content.parts = [mock_text_part, mock_function_part]
    
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Expected function declaration
    expected_function_declaration = types.FunctionDeclaration(
        name="add_memory",
        description="Add a memory",
        parameters={
            "type": "object",
            "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
            "required": ["data"],
        }
    )
    
    expected_tool = types.Tool(function_declarations=[expected_function_declaration])
    
    expected_tool_config = types.ToolConfig(
        function_calling_config=types.FunctionCallingConfig(
            mode=types.FunctionCallingConfigMode.AUTO,
            allowed_function_names=None
        )
    )

    mock_gemini_client.models.generate_content.assert_called_once_with(
        model="gemini-2.0-flash",
        contents=[
            types.Content(
                parts=[types.Part(text="Add a new memory: Today is a sunny day.")],
                role="user"
            )
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=100,
            top_p=1.0,
            system_instruction="You are a helpful assistant.",
            tools=[expected_tool],
            tool_config=expected_tool_config
        )
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
