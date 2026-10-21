import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.nvidia import NvidiaConfig
from mem0.llms.nvidia import NvidiaLLM
from mem0.utils.factory import LlmFactory


@pytest.fixture
def mock_nvidia_client():
    with patch("mem0.llms.nvidia.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_nvidia_llm_default_base_url():
    """Default config uses NVIDIA official base URL."""
    config = BaseLlmConfig(
        model="meta/llama-3.1-8b-instruct", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = NvidiaLLM(config)
    # OpenAI client may normalize URL with trailing slash
    assert str(llm.client.base_url).rstrip("/") == "https://integrate.api.nvidia.com/v1"


def test_nvidia_llm_env_base_url():
    """Config uses NVIDIA_API_BASE env variable when set."""
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["NVIDIA_API_BASE"] = provider_base_url
    try:
        config = NvidiaConfig(
            model="meta/llama-3.1-8b-instruct",
            temperature=0.7,
            max_tokens=100,
            top_p=1.0,
            api_key="api_key",
        )
        llm = NvidiaLLM(config)
        assert str(llm.client.base_url).rstrip("/") == provider_base_url.rstrip("/")
    finally:
        os.environ.pop("NVIDIA_API_BASE", None)


def test_nvidia_llm_config_base_url():
    """Config uses nvidia_base_url when provided."""
    config_base_url = "https://api.config.com/v1/"
    config = NvidiaConfig(
        model="meta/llama-3.1-8b-instruct",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        nvidia_base_url=config_base_url,
    )
    llm = NvidiaLLM(config)
    assert str(llm.client.base_url).rstrip("/") == config_base_url.rstrip("/")


def test_nvidia_llm_default_model(mock_nvidia_client):
    """Default model is meta/llama-3.1-8b-instruct when not specified."""
    config = NvidiaConfig(temperature=0.7, max_tokens=100, api_key="api_key")
    llm = NvidiaLLM(config)
    assert llm.config.model == "meta/llama-3.1-8b-instruct"


def test_nvidia_llm_env_api_key():
    """Uses NVIDIA_API_KEY env when api_key not in config."""
    os.environ["NVIDIA_API_KEY"] = "env-api-key"
    try:
        with patch("mem0.llms.nvidia.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            config = NvidiaConfig(model="meta/llama-3.1-8b-instruct", api_key=None)
            NvidiaLLM(config)
            mock_openai.assert_called_once_with(
                api_key="env-api-key",
                base_url="https://integrate.api.nvidia.com/v1",
            )
    finally:
        os.environ.pop("NVIDIA_API_KEY", None)


def test_generate_response_without_tools(mock_nvidia_client):
    """generate_response returns text when no tools provided."""
    config = BaseLlmConfig(
        model="meta/llama-3.1-8b-instruct", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = NvidiaLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_nvidia_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_nvidia_client.chat.completions.create.assert_called_once_with(
        model="meta/llama-3.1-8b-instruct", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_nvidia_client):
    """generate_response returns tool_calls when tools provided."""
    config = BaseLlmConfig(
        model="meta/llama-3.1-8b-instruct", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = NvidiaLLM(config)
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
    mock_nvidia_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_nvidia_client.chat.completions.create.assert_called_once_with(
        model="meta/llama-3.1-8b-instruct",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        tools=tools,
        tool_choice="auto",
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_with_response_format(mock_nvidia_client):
    """generate_response passes response_format to the API."""
    config = BaseLlmConfig(
        model="meta/llama-3.1-8b-instruct", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = NvidiaLLM(config)
    messages = [{"role": "user", "content": "Return JSON."}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
    mock_nvidia_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format=response_format)

    mock_nvidia_client.chat.completions.create.assert_called_once_with(
        model="meta/llama-3.1-8b-instruct",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )


def test_factory_creates_nvidia_llm(mock_nvidia_client):
    """LlmFactory.create returns NvidiaLLM for provider 'nvidia'."""
    llm = LlmFactory.create("nvidia", {"model": "meta/llama-3.1-8b-instruct", "api_key": "test-key"})
    assert isinstance(llm, NvidiaLLM)
    assert llm.config.model == "meta/llama-3.1-8b-instruct"
