import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.atlascloud import AtlasCloudConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.atlascloud import AtlasCloudLLM
from mem0.utils.factory import LlmFactory

DEFAULT_MODEL = "deepseek-ai/DeepSeek-V3.1-Terminus"


@pytest.fixture
def mock_atlascloud_client():
    with patch("mem0.llms.atlascloud.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_atlascloud_llm_default_base_url():
    """Default config uses the Atlas Cloud official base URL."""
    config = BaseLlmConfig(model=DEFAULT_MODEL, temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AtlasCloudLLM(config)
    # OpenAI client may normalize URL with trailing slash
    assert str(llm.client.base_url).rstrip("/") == "https://api.atlascloud.ai/v1"


def test_atlascloud_llm_env_base_url():
    """Config uses ATLASCLOUD_API_BASE env variable when set."""
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["ATLASCLOUD_API_BASE"] = provider_base_url
    try:
        config = AtlasCloudConfig(model=DEFAULT_MODEL, temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
        llm = AtlasCloudLLM(config)
        assert str(llm.client.base_url).rstrip("/") == provider_base_url.rstrip("/")
    finally:
        os.environ.pop("ATLASCLOUD_API_BASE", None)


def test_atlascloud_llm_config_base_url():
    """Config uses atlascloud_base_url when provided."""
    config_base_url = "https://api.config.com/v1/"
    config = AtlasCloudConfig(
        model=DEFAULT_MODEL,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        atlascloud_base_url=config_base_url,
    )
    llm = AtlasCloudLLM(config)
    assert str(llm.client.base_url).rstrip("/") == config_base_url.rstrip("/")


def test_atlascloud_llm_default_model(mock_atlascloud_client):
    """Default model is used when not specified."""
    config = AtlasCloudConfig(temperature=0.7, max_tokens=100, api_key="api_key")
    llm = AtlasCloudLLM(config)
    assert llm.config.model == DEFAULT_MODEL


def test_atlascloud_llm_env_api_key():
    """Uses ATLASCLOUD_API_KEY env when api_key not in config."""
    os.environ["ATLASCLOUD_API_KEY"] = "env-api-key"
    try:
        with patch("mem0.llms.atlascloud.OpenAI") as mock_openai:
            mock_client = Mock()
            mock_openai.return_value = mock_client
            config = AtlasCloudConfig(model=DEFAULT_MODEL, api_key=None)
            AtlasCloudLLM(config)
            mock_openai.assert_called_once_with(
                api_key="env-api-key",
                base_url="https://api.atlascloud.ai/v1",
            )
    finally:
        os.environ.pop("ATLASCLOUD_API_KEY", None)


def test_generate_response_without_tools(mock_atlascloud_client):
    """generate_response returns text when no tools provided."""
    config = BaseLlmConfig(model=DEFAULT_MODEL, temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AtlasCloudLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_atlascloud_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_atlascloud_client.chat.completions.create.assert_called_once_with(
        model=DEFAULT_MODEL, messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_atlascloud_client):
    """generate_response returns tool_calls when tools provided."""
    config = BaseLlmConfig(model=DEFAULT_MODEL, temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AtlasCloudLLM(config)
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
    mock_atlascloud_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_atlascloud_client.chat.completions.create.assert_called_once_with(
        model=DEFAULT_MODEL,
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


def test_generate_response_with_response_format(mock_atlascloud_client):
    """generate_response passes response_format to the API."""
    config = BaseLlmConfig(model=DEFAULT_MODEL, temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = AtlasCloudLLM(config)
    messages = [{"role": "user", "content": "Return JSON."}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
    mock_atlascloud_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format=response_format)

    mock_atlascloud_client.chat.completions.create.assert_called_once_with(
        model=DEFAULT_MODEL,
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )


def test_factory_creates_atlascloud_llm(mock_atlascloud_client):
    """LlmFactory.create returns AtlasCloudLLM for provider 'atlascloud'."""
    llm = LlmFactory.create("atlascloud", {"model": DEFAULT_MODEL, "api_key": "test-key"})
    assert isinstance(llm, AtlasCloudLLM)
    assert llm.config.model == DEFAULT_MODEL
