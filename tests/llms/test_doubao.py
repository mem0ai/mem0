from unittest.mock import Mock, patch
import os
import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.doubao import DouBaoLLM


@pytest.fixture
def mock_doubao_client():
    with patch("mem0.llms.doubao.Ark") as mock_ark:
        mock_client = Mock()
        mock_ark.return_value = mock_client
        yield mock_client


def test_ark_llm_base_url():
    # case1: default config: with ark official base url
    model = "your endpoint"
    api_key = "your api_key"
    config = BaseLlmConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key=api_key)
    llm = DouBaoLLM(config)
    # Note: ark client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client._base_url) == "https://ark.cn-beijing.volces.com/api/v3/"
    
    # case2: with config.ark_base_url
    config_base_url = "https://ark.cn-beijing.volces.com/api/v3"
    config = BaseLlmConfig(
        model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key=api_key, openai_base_url=config_base_url
    )
    llm = DouBaoLLM(config)
    
    assert str(llm.client._base_url) == config_base_url + "/"


def test_generate_response_without_tools(mock_doubao_client):
    model = "your endpoint"
    api_key = "your api_key"
    config = BaseLlmConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key=api_key)
    llm = DouBaoLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]
    
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_doubao_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)
    print(f"args {mock_doubao_client.chat.completions.create.call_args}")
    
    mock_doubao_client.chat.completions.create.assert_called_once_with(
        model=model, messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    ) # TODO bugfix api key

    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_doubao_client):
    model = "your endpoint"
    api_key = "your api_key"
    config = BaseLlmConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key=api_key)
    llm = DouBaoLLM(config)
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
    mock_doubao_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_doubao_client.chat.completions.create.assert_called_once_with(
        model=model, messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools, tool_choice="auto"
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}
