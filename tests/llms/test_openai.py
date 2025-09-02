import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai import OpenAILLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_openai_llm_base_url():
    # case1: default config: with openai official base url
    config = OpenAIConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == "https://api.openai.com/v1/"

    # case2: with env variable OPENAI_API_BASE
    provider_base_url = "https://api.provider.com/v1"
    os.environ["OPENAI_BASE_URL"] = provider_base_url
    config = OpenAIConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == provider_base_url + "/"

    # case3: with config.openai_base_url
    config_base_url = "https://api.config.com/v1"
    config = OpenAIConfig(
        model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key", openai_base_url=config_base_url
    )
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == config_base_url + "/"


def test_generate_response_without_tools(mock_openai_client):
    config = OpenAIConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, store=False
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = OpenAIConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
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
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools, tool_choice="auto", store=False
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_response_callback_invocation(mock_openai_client):
    # Setup mock callback
    mock_callback = Mock()
    
    config = OpenAIConfig(model="gpt-4o", response_callback=mock_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test callback"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Call method
    llm.generate_response(messages)
    
    # Verify callback called with correct arguments
    mock_callback.assert_called_once()
    args = mock_callback.call_args[0]
    assert args[0] is llm  # llm_instance
    assert args[1] == mock_response  # raw_response
    assert "messages" in args[2]  # params


def test_no_response_callback(mock_openai_client):
    config = OpenAIConfig(model="gpt-4o")
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test no callback"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Should complete without calling any callback
    response = llm.generate_response(messages)
    assert response == "Response"
    
    # Verify no callback is set
    assert llm.config.response_callback is None


def test_callback_exception_handling(mock_openai_client):
    # Callback that raises exception
    def faulty_callback(*args):
        raise ValueError("Callback error")
    
    config = OpenAIConfig(model="gpt-4o", response_callback=faulty_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test exception"}]
    
    # Mock response
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Expected response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    # Should complete without raising
    response = llm.generate_response(messages)
    assert response == "Expected response"
    
    # Verify callback was called (even though it raised an exception)
    assert llm.config.response_callback is faulty_callback


def test_callback_with_tools(mock_openai_client):
    mock_callback = Mock()
    config = OpenAIConfig(model="gpt-4o", response_callback=mock_callback)
    llm = OpenAILLM(config)
    messages = [{"role": "user", "content": "Test tools"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "test_tool",
                "description": "A test tool",
                "parameters": {
                    "type": "object",
                    "properties": {"param1": {"type": "string"}},
                    "required": ["param1"],
                },
            }
        }
    ]
    
    # Mock tool response
    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "Tool response"
    mock_tool_call = Mock()
    mock_tool_call.function.name = "test_tool"
    mock_tool_call.function.arguments = '{"param1": "value1"}'
    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.chat.completions.create.return_value = mock_response
    
    llm.generate_response(messages, tools=tools)
    
    # Verify callback called with tool response
    mock_callback.assert_called_once()
    # Check that tool_calls exists in the message
    assert hasattr(mock_callback.call_args[0][1].choices[0].message, 'tool_calls')
