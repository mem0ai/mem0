import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.vllm import VllmLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.vllm.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_vllm_llm_initialization():
    """Test vLLM LLM initialization with default configuration"""
    config = BaseLlmConfig(
        model="meta-llama/Llama-3.1-8B-Instruct",
        temperature=0.1,
        max_tokens=2000,
        top_p=0.9,
        api_key="vllm-api-key"
    )
    llm = VllmLLM(config)
    
    assert llm.config.model == "meta-llama/Llama-3.1-8B-Instruct"
    assert llm.config.temperature == 0.1
    assert llm.config.max_tokens == 2000


def test_vllm_llm_base_url_configuration():
    """Test vLLM base URL configuration from different sources"""
    
    # Test default base URL
    config = BaseLlmConfig(model="meta-llama/Llama-3.1-8B-Instruct", api_key="test-key")
    with patch("mem0.llms.vllm.OpenAI") as mock_openai:
        VllmLLM(config)
        mock_openai.assert_called_once_with(
            base_url="http://localhost:8000/v1",
            api_key="test-key"
        )
    
    # Test config-specified base URL
    config = BaseLlmConfig(
        model="meta-llama/Llama-3.1-8B-Instruct",
        api_key="test-key",
        vllm_base_url="http://custom-vllm:8000/v1"
    )
    with patch("mem0.llms.vllm.OpenAI") as mock_openai:
        VllmLLM(config)
        mock_openai.assert_called_once_with(
            base_url="http://custom-vllm:8000/v1",
            api_key="test-key"
        )
    
    # Test environment variable
    os.environ["VLLM_BASE_URL"] = "http://env-vllm:8000/v1"
    config = BaseLlmConfig(model="meta-llama/Llama-3.1-8B-Instruct", api_key="test-key")
    with patch("mem0.llms.vllm.OpenAI") as mock_openai:
        VllmLLM(config)
        mock_openai.assert_called_once_with(
            base_url="http://env-vllm:8000/v1",
            api_key="test-key"
        )
    # Clean up
    del os.environ["VLLM_BASE_URL"]


def test_generate_response_without_tools(mock_openai_client):
    """Test basic response generation without tools"""
    config = BaseLlmConfig(
        model="meta-llama/Llama-3.1-8B-Instruct",
        temperature=0.1,
        max_tokens=2000,
        top_p=0.9
    )
    llm = VllmLLM(config)
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="meta-llama/Llama-3.1-8B-Instruct",
        messages=messages,
        temperature=0.1,
        max_tokens=2000,
        top_p=0.9
    )
    assert response == "I'm doing well, thank you!"





def test_generate_response_with_tools(mock_openai_client):
    """Test response generation with tool calling"""
    config = BaseLlmConfig(
        model="meta-llama/Llama-3.1-8B-Instruct",
        temperature=0.1,
        max_tokens=2000
    )
    llm = VllmLLM(config)
    
    messages = [
        {"role": "user", "content": "Add a memory: Today is sunny."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_memory",
                "description": "Add a memory",
                "parameters": {
                    "type": "object",
                    "properties": {"data": {"type": "string"}},
                    "required": ["data"],
                },
            },
        }
    ]

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "I've added the memory."

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "Today is sunny."}'

    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_openai_client.chat.completions.create.assert_called_once()
    call_args = mock_openai_client.chat.completions.create.call_args
    assert call_args.kwargs["tools"] == tools
    assert call_args.kwargs["tool_choice"] == "auto"

    assert response["content"] == "I've added the memory."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is sunny."}


def test_generate_response_error_handling(mock_openai_client):
    """Test error handling in response generation"""
    config = BaseLlmConfig(model="meta-llama/Llama-3.1-8B-Instruct")
    llm = VllmLLM(config)
    
    messages = [{"role": "user", "content": "Test message"}]
    
    # Mock an exception
    mock_openai_client.chat.completions.create.side_effect = Exception("Connection error")
    
    with pytest.raises(RuntimeError, match="vLLM inference failed: Connection error"):
        llm.generate_response(messages)
