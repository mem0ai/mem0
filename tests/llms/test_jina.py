from unittest.mock import Mock, patch
import os
import pytest
from requests.exceptions import RequestException

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.jina import JinaLLM


@pytest.fixture
def mock_jina_client():
    with patch("mem0.llms.jina.requests.post") as mock_post:
        mock_response = Mock()
        mock_response.json.return_value = {
            "chatId": "test-chat-id",
            "inputMessageId": "test-input-message-id",
            "responseMessageId": "test-response-message-id",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "This is a test response from Jina AI Chat."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30
            }
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response
        yield mock_post


def test_jina_llm_init():
    # Test with explicit API key in config
    config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
    with patch.dict(os.environ, {}, clear=True):
        llm = JinaLLM(config)
        assert llm.api_key == "test-api-key"
        assert llm.base_url == "https://api.chat.jina.ai/v1/chat"
        assert llm.headers == {"Content-Type": "application/json", "Authorization": "Bearer test-api-key"}

    # Test with environment variable API key
    with patch.dict(os.environ, {"JINACHAT_API_KEY": "env-api-key"}, clear=True):
        config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0)
        llm = JinaLLM(config)
        assert llm.api_key == "env-api-key"

    # Test with custom base URL
    config = BaseLlmConfig(
        model="jina-chat-v1", 
        temperature=0.7, 
        max_tokens=100, 
        top_p=1.0, 
        api_key="test-api-key", 
        jina_base_url="https://custom.jina.ai/v1"
    )
    llm = JinaLLM(config)
    assert llm.base_url == "https://custom.jina.ai/v1"

    # Test with environment variable base URL
    with patch.dict(os.environ, {"JINACHAT_API_BASE": "https://env.jina.ai/v1"}, clear=True):
        config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
        llm = JinaLLM(config)
        assert llm.base_url == "https://env.jina.ai/v1"


def test_generate_response_without_tools(mock_jina_client):
    config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
    llm = JinaLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    response = llm.generate_response(messages)
    
    # Verify the response is correctly parsed
    assert response == "This is a test response from Jina AI Chat."
    
    # Verify the correct API call was made
    mock_jina_client.assert_called_once_with(
        f"{llm.base_url}/completions",
        headers=llm.headers,
        json={
            "model": "jina-chat-v1",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 1.0,
        }
    )


def test_generate_response_with_tools(mock_jina_client):
    config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
    llm = JinaLLM(config)
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

    # Update mock_jina_client to include tool_calls in the response
    mock_jina_client.return_value.json.return_value = {
        "chatId": "test-chat-id",
        "inputMessageId": "test-input-message-id",
        "responseMessageId": "test-response-message-id",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "I've added the memory for you.",
                    "tool_calls": [
                        {
                            "id": "call_abc123",
                            "type": "function",
                            "function": {
                                "name": "add_memory",
                                "arguments": '{"data": "Today is a sunny day."}'
                            }
                        }
                    ]
                },
                "finish_reason": "tool_calls"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }

    response = llm.generate_response(messages, tools=tools)
    
    # Verify the response is correctly parsed
    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
    
    # Verify the correct API call was made
    mock_jina_client.assert_called_once_with(
        f"{llm.base_url}/completions",
        headers=llm.headers,
        json={
            "model": "jina-chat-v1",
            "messages": messages,
            "temperature": 0.7,
            "max_tokens": 100,
            "top_p": 1.0,
            "tools": tools,
            "tool_choice": "auto"
        }
    )


def test_error_handling(mock_jina_client):
    config = BaseLlmConfig(model="jina-chat-v1", temperature=0.7, max_tokens=100, top_p=1.0, api_key="test-api-key")
    llm = JinaLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]
    
    # Make the request raise an exception
    mock_error_response = Mock()
    mock_error_response.json.return_value = {"error": "Invalid API key"}
    mock_error_response.status_code = 401
    
    request_exception = RequestException("Error occurred")
    request_exception.response = mock_error_response
    
    mock_jina_client.side_effect = request_exception
    
    # Try to generate a response, which should raise an exception
    with pytest.raises(Exception) as excinfo:
        llm.generate_response(messages)
    
    # Verify the exception message contains the API error
    assert "API Error: Invalid API key" in str(excinfo.value) 