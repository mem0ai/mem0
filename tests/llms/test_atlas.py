import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.atlas import AtlasConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.atlas import AtlasLLM


@pytest.fixture
def mock_atlas_client():
    with patch("mem0.llms.atlas.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_atlas_llm_base_url():
    # case1: default config falls back to the Atlas Cloud base url
    config = BaseLlmConfig(
        model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = AtlasLLM(config)
    assert str(llm.client.base_url) == "https://api.atlascloud.ai/v1/"

    # case2: with env variable ATLASCLOUD_API_BASE
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["ATLASCLOUD_API_BASE"] = provider_base_url
    config = AtlasConfig(
        model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = AtlasLLM(config)
    assert str(llm.client.base_url) == provider_base_url
    del os.environ["ATLASCLOUD_API_BASE"]

    # case3: with config.atlas_base_url
    config_base_url = "https://api.config.com/v1/"
    config = AtlasConfig(
        model="deepseek-ai/deepseek-v4-pro",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        atlas_base_url=config_base_url,
    )
    llm = AtlasLLM(config)
    assert str(llm.client.base_url) == config_base_url


def test_atlas_llm_default_model():
    config = AtlasConfig(api_key="api_key")
    llm = AtlasLLM(config)
    assert llm.config.model == "deepseek-ai/deepseek-v4-pro"


def test_generate_response_without_tools(mock_atlas_client):
    config = BaseLlmConfig(model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AtlasLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_atlas_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_atlas_client.chat.completions.create.assert_called_once_with(
        model="deepseek-ai/deepseek-v4-pro", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_atlas_client):
    config = BaseLlmConfig(model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AtlasLLM(config)
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
    mock_atlas_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_atlas_client.chat.completions.create.assert_called_once_with(
        model="deepseek-ai/deepseek-v4-pro",
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


def test_generate_response_with_response_format(mock_atlas_client):
    config = BaseLlmConfig(model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AtlasLLM(config)
    messages = [
        {"role": "system", "content": "You are a memory extraction assistant."},
        {"role": "user", "content": "I like hiking on weekends."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"facts": ["User likes hiking on weekends"]}'))]
    mock_atlas_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    mock_atlas_client.chat.completions.create.assert_called_once_with(
        model="deepseek-ai/deepseek-v4-pro",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )
    assert response == '{"facts": ["User likes hiking on weekends"]}'


def test_generate_response_without_response_format(mock_atlas_client):
    config = BaseLlmConfig(model="deepseek-ai/deepseek-v4-pro", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AtlasLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Why did the chicken cross the road?"))]
    mock_atlas_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    call_kwargs = mock_atlas_client.chat.completions.create.call_args[1]
    assert "response_format" not in call_kwargs
    assert response == "Why did the chicken cross the road?"
