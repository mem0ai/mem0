from unittest.mock import Mock, patch

import pytest
from google.genai import types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_client():
    with patch("mem0.llms.gemini.genai") as mock_client_class:
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
    mock_embedding = Mock()
    mock_embedding.values = [0.1, 0.2, 0.3]

    mock_response = Mock()
    mock_response.candidates = [Mock()]
    mock_response.candidates[0].content.parts = [Mock()]
    mock_response.candidates[0].content.parts[0].text = "I'm doing well, thank you for asking!"

    mock_gemini_client.models.generate_content.return_value = mock_response
    mock_content = Mock(parts=[mock_part])
    mock_message = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_message])
    mock_gemini_client.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    mock_gemini_client.generate_content.assert_called_once_with(
        contents=[
            {"parts": "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: You are a helpful assistant.", "role": "user"},
            {"parts": "Hello, how are you?", "role": "user"},
        ],
        config=types.GenerateContentConfig(
              temperature=0.7, 
              max_output_tokens=100, 
              top_p=1.0,
              tools=None,
              tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    allowed_function_names=None,
                    mode="auto"
                
                )
            )
    )   )
    
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
    mock_gemini_client.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_gemini_client.generate_content.assert_called_once_with(
        contents=[
            {
                "parts": "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: You are a helpful assistant.",
                "role": "user"
            },
            {
                "parts": "Add a new memory: Today is a sunny day.",
                "role": "user"
            },
        ],
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=100,
            top_p=1.0,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name="add_memory",
                            description="Add a memory",
                            parameters={
                                "type": "object",
                                "properties": {
                                    "data": {
                                        "type": "string",
                                        "description": "Data to add to memory"
                                    }
                                },
                                "required": ["data"]
                            }
                        )
                    ]
                )
            ],
            tool_config=types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    allowed_function_names=None,
                    mode="auto"
                )
            )
        )
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
