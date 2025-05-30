from unittest.mock import Mock, patch, MagicMock

import pytest
# Updated imports for the new SDK
from google.genai.types import (
    GenerationConfig,
    Tool,
    FunctionDeclaration,
    ToolConfig,
    FunctionCallingConfig
)
# protos is no longer needed for FunctionCall as it's directly an attribute with name/args
# from google.generativeai import protos - removed

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_setup(): # Renamed fixture
    # Patch genai.Client within the mem0.llms.gemini module
    with patch("mem0.llms.gemini.genai.Client") as mock_client_constructor:
        mock_client_instance = MagicMock(name="client_instance")

        # This is the object that will be returned by generate_content
        mock_response_payload = MagicMock(name="response_payload_obj")

        mock_client_instance.models = MagicMock(name="client_instance.models")
        mock_client_instance.models.generate_content = MagicMock(
            name="client_instance.models.generate_content",
            return_value=mock_response_payload
        )

        mock_client_constructor.return_value = mock_client_instance
        # Yield both the client mock and the direct response payload mock
        yield mock_client_instance, mock_response_payload


def test_generate_response_without_tools(mock_gemini_setup: tuple):
    mock_gemini_client, mock_response_payload = mock_gemini_setup # Unpack
    config = BaseLlmConfig(model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    # Use Mock instead of MagicMock for payload simulation
    mock_candidate = Mock(name="mock_candidate_rt")
    mock_candidate_content = Mock(name="mock_candidate_content_rt")
    mock_part = Mock(name="mock_part_rt")

    mock_part.text = "I'm doing well, thank you for asking!"
    mock_part.function_call = None

    mock_candidate_content.parts = [mock_part]
    mock_candidate.content = mock_candidate_content
    # mock_response_payload is already a MagicMock from the fixture, configure its attributes
    mock_response_payload.candidates = list([mock_candidate]) # Explicitly use list()

    response = llm.generate_response(messages)

    mock_gemini_client.models.generate_content.assert_called_once_with(
        model="gemini-1.5-flash-latest", # Added model argument check
        contents=[
            {'parts': [{'text': "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: You are a helpful assistant."}], 'role': 'user'},
            {'parts': [{'text': "Hello, how are you?"}], 'role': 'user'},
        ],
        generation_config=GenerationConfig(temperature=0.7, max_output_tokens=100, top_p=1.0),
        tools=None,
        tool_config=ToolConfig(function_calling_config=FunctionCallingConfig(mode="AUTO")) # Changed to string
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_gemini_setup: tuple):
    mock_gemini_client, mock_response_payload = mock_gemini_setup # Unpack
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

    # Use Mock for payload simulation
    mock_function_call = Mock(name="mock_function_call")
    mock_function_call.name = "add_memory"
    mock_function_call.args = {"data": "Today is a sunny day."}

    mock_function_part = Mock(name="mock_function_part")
    mock_function_part.function_call = mock_function_call
    mock_function_part.text = None

    mock_text_part = Mock(name="mock_text_part")
    mock_text_part.text = "I've added the memory for you."
    mock_text_part.function_call = None

    mock_response_content_parts = [mock_text_part, mock_function_part]

    mock_candidate_content_tool = Mock(parts=mock_response_content_parts, name="cand_content_tool")
    mock_candidate_tool = Mock(content=mock_candidate_content_tool, name="cand_tool")
    mock_response_payload.candidates = list([mock_candidate_tool]) # Explicitly use list()

    response = llm.generate_response(messages, tools=tools)

    expected_tools = [
        Tool(function_declarations=[
            FunctionDeclaration(
                name="add_memory",
                description="Add a memory",
                parameters={
                    "type": "object",
                    "properties": {"data": {"type": "string", "description": "Data to add to memory"}},
                    "required": ["data"],
                }
            )
        ])
    ]

    mock_gemini_client.models.generate_content.assert_called_once_with(
        model="gemini-1.5-flash-latest", # Added model argument check
        contents=[
            {'parts': [{'text': "THIS IS A SYSTEM PROMPT. YOU MUST OBEY THIS: You are a helpful assistant."}], 'role': 'user'},
            {'parts': [{'text': "Add a new memory: Today is a sunny day."}], 'role': 'user'},
        ],
        generation_config=GenerationConfig(temperature=0.7, max_output_tokens=100, top_p=1.0),
        tools=expected_tools,
        tool_config=ToolConfig(function_calling_config=FunctionCallingConfig(mode="AUTO")) # Changed to string
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    # The new _parse_response converts args to dict: dict(part.function_call.args)
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_with_json_format(mock_gemini_setup: tuple):
    mock_gemini_client, mock_response_payload = mock_gemini_setup # Unpack
    config = BaseLlmConfig(model="gemini-1.5-flash-latest")
    llm = GeminiLLM(config)
    messages = [{"role": "user", "content": "Get user data for ID 123"}]
    response_format = {
        "type": "json_object",
        "schema": {
            "type": "object",
            "properties": {"user_id": {"type": "integer"}, "name": {"type": "string"}},
        }
    }

    # Use Mock for payload simulation
    mock_candidate_json = Mock(name="mock_candidate_json_rt")
    mock_candidate_content_json = Mock(name="mock_candidate_content_json_rt")
    mock_part_json = Mock(name="mock_part_json_rt")

    mock_part_json.text = '{"user_id": 123, "name": "John Doe"}'
    mock_part_json.function_call = None

    mock_candidate_content_json.parts = [mock_part_json]
    mock_candidate_json.content = mock_candidate_content_json
    mock_response_payload.candidates = list([mock_candidate_json]) # Explicitly use list()

    response = llm.generate_response(messages, response_format=response_format)

    expected_gen_config = GenerationConfig(
        temperature=config.temperature, # from default BaseLlmConfig
        max_output_tokens=config.max_tokens, # from default BaseLlmConfig
        top_p=config.top_p, # from default BaseLlmConfig
        response_mime_type="application/json",
        response_schema=response_format["schema"]
    )

    mock_gemini_client.models.generate_content.assert_called_once_with(
        model=config.model, # Added model argument check
        contents=[{'parts': [{'text': "Get user data for ID 123"}], 'role': 'user'}],
        generation_config=expected_gen_config,
        tools=None,
        tool_config=ToolConfig(function_calling_config=FunctionCallingConfig(mode="AUTO")) # Changed to string
    )
    assert response == '{"user_id": 123, "name": "John Doe"}'
