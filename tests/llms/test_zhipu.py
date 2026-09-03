import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.zhipu import ZhipuConfig
from mem0.llms.zhipu import ZhipuLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.zhipu.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_zhipu_llm_base_url():
    # case1: default config: with zhipu official base url
    config = ZhipuConfig(model="glm-4", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = ZhipuLLM(config)
    assert str(llm.client.base_url) == "https://open.bigmodel.cn/api/paas/v4/"

    # case2: with env variable ZHIPU_API_BASE
    provider_base_url = "https://custom-zhipu.example.com/v4"
    os.environ["ZHIPU_API_BASE"] = provider_base_url
    config = ZhipuConfig(model="glm-4", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key")
    llm = ZhipuLLM(config)
    assert str(llm.client.base_url) == provider_base_url + "/"
    del os.environ["ZHIPU_API_BASE"]

    # case3: with config.zhipu_base_url
    config_base_url = "https://api.config.com/v4"
    config = ZhipuConfig(
        model="glm-4", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key", zhipu_base_url=config_base_url
    )
    llm = ZhipuLLM(config)
    assert str(llm.client.base_url) == config_base_url + "/"


def test_generate_response_without_tools(mock_openai_client):
    config = ZhipuConfig(model="glm-4-plus", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = ZhipuLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="glm-4-plus", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = ZhipuConfig(model="glm-4-plus", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = ZhipuLLM(config)
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
        model="glm-4-plus", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_default_model(mock_openai_client):
    config = ZhipuConfig()
    llm = ZhipuLLM(config)
    assert llm.config.model == "glm-4"


def test_base_llm_config_conversion(mock_openai_client):
    """Test that BaseLlmConfig is correctly converted to ZhipuConfig."""
    base_config = BaseLlmConfig(
        model="glm-4-flash",
        temperature=0.5,
        api_key="test_key",
        max_tokens=500,
        top_p=0.9,
    )
    llm = ZhipuLLM(base_config)
    assert isinstance(llm.config, ZhipuConfig)
    assert llm.config.model == "glm-4-flash"
    assert llm.config.temperature == 0.5
    assert llm.config.api_key == "test_key"
    assert llm.config.max_tokens == 500
    assert llm.config.top_p == 0.9
