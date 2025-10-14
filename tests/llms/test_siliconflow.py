import os
from unittest.mock import Mock, patch
from openai import APIError

import pytest

from mem0.configs.llms.siliconflow import SiliconflowConfig
from mem0.openai_error_codes import OpenAPIErrorCode
from mem0.llms.siliconflow import SiliconflowLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.siliconflow.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_siliconflow_llm_base_url():
    # case1: default config: with siliconflow official base url
    config = SiliconflowConfig(model="tencent/Hunyuan-MT-7B", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = SiliconflowLLM(config)
    assert str(llm.client.base_url) == "https://api.siliconflow.com/v1/"

    # case2: with env variable SILICONFLOW_BASE_URL
    provider_base_url = "https://api.provider.com/v1"
    os.environ["SILICONFLOW_BASE_URL"] = provider_base_url
    config = SiliconflowConfig(model="tencent/Hunyuan-MT-7B", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = SiliconflowLLM(config)
    assert str(llm.client.base_url) == provider_base_url + "/"

    # case3: with config.siliconflow_base_url
    config_base_url = "https://api.config.com/v1"
    config = SiliconflowConfig(
        model="tencent/Hunyuan-MT-7B", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key", base_url=config_base_url
    )
    llm = SiliconflowLLM(config)
    assert str(llm.client.base_url) == config_base_url + "/"


def test_generate_response(mock_openai_client):
    config = SiliconflowConfig(model="tencent/Hunyuan-MT-7B", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = SiliconflowLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="tencent/Hunyuan-MT-7B",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = SiliconflowConfig(model="tencent/Hunyuan-MT-7B", temperature=0.1, max_tokens=2000, top_p=0.1)
    llm = SiliconflowLLM(config)
    messages = [{"role": "user", "content": "What's the weather in Boston?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_current_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    # Mock the response from the OpenAI client
    mock_tool_call = Mock()
    mock_tool_call.function.name = "get_current_weather"
    mock_tool_call.function.arguments = '{"location": "Boston, MA"}'

    mock_message = Mock()
    mock_message.tool_calls = [mock_tool_call]

    mock_choice = Mock()
    mock_choice.message = mock_message

    mock_response = Mock()
    mock_response.choices = [mock_choice]
    mock_openai_client.chat.completions.create.return_value = mock_response

    # Call the method being tested
    response = llm.generate_response(messages, tools=tools)

    # Assert that the create method was called correctly
    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="tencent/Hunyuan-MT-7B",
        messages=messages,
        temperature=0.1,
        max_tokens=2000,
        top_p=0.1,
        tools=tools,
    )

    # Assert that the response is what we expect
    expected_response = [
        {
            "name": "get_current_weather",
            "arguments": {"location": "Boston, MA"},
        }
    ]
    assert response == expected_response


def test_generate_response_with_tool_error_fallback(mock_openai_client):
    """
    Test that the LLM falls back to a non-tool call when the model doesn't support function calling.
    """
    config = SiliconflowConfig(model="some-model-without-tool-support")
    llm = SiliconflowLLM(config)
    messages = [{"role": "user", "content": "What's the weather in Boston?"}]
    tools = [{"type": "function", "function": {"name": "get_weather"}}]

    # Mock the APIError for the first call
    error = APIError("Function call is not supported for this model.", request=Mock(), body=None)
    error.code = OpenAPIErrorCode.FUNCTION_CALL_NOT_SUPPORTED.value
    
    # Mock the successful response for the fallback call
    fallback_response = Mock()
    fallback_response.choices = [Mock(message=Mock(content="I can't use tools."))]

    mock_openai_client.chat.completions.create.side_effect = [
        error,
        fallback_response,
    ]

    response = llm.generate_response(messages, tools=tools)

    assert response == "I can't use tools."
    assert mock_openai_client.chat.completions.create.call_count == 2
    
    # Check the first call was with tools
    first_call_args, first_call_kwargs = mock_openai_client.chat.completions.create.call_args_list[0]
    assert "tools" in first_call_kwargs
    
    # Check the second call was without tools
    second_call_args, second_call_kwargs = mock_openai_client.chat.completions.create.call_args_list[1]
    assert "tools" not in second_call_kwargs
