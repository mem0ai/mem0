import os
from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.jan import JanConfig
from mem0.llms.jan import JanLLM

jan_api_key = "JanServer"
jan_base_url = "http://localhost:1337/v1/"
model = "openai_gpt-oss-20b-IQ2_M"

@pytest.fixture
def mock_jan_client():
    with patch("mem0.llms.jan.OpenAI") as mock_jan:
        mock_client = Mock()
        mock_jan.return_value = mock_client
        yield mock_client


def test_jan_llm_base_url():
    # case1: default config: with jan local base url
    config = JanConfig(model=model, 
                       temperature=0.7, 
                       max_tokens=100, 
                       top_p=1.0, 
                       api_key=jan_api_key)
    llm = JanLLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == jan_base_url

    # case2: with env variable JAN_API_BASE
    os.environ["JAN_BASE_URL"] = jan_base_url
    config = JanConfig(model="openai_gpt-oss-20b-IQ2_M", temperature=0.7, max_tokens=100, top_p=1.0, api_key="SimaJanServer")
    llm = JanLLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == jan_base_url

    # case3: with config.jan_base_url
    config = JanConfig(
        model="openai_gpt-oss-20b-IQ2_M", temperature=0.7, max_tokens=100, top_p=1.0, api_key=jan_api_key, jan_base_url=jan_base_url
    )
    llm = JanLLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == jan_base_url


def test_generate_response_without_tools(mock_jan_client):
    config = JanConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key = jan_api_key)
    llm = JanLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_jan_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_jan_client.chat.completions.create.assert_called_once_with(
        model=model, messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_jan_client):
    config = JanConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0, api_key=jan_api_key)
    llm = JanLLM(config)
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
    mock_jan_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)
    print(response)

    mock_jan_client.chat.completions.create.assert_called_once_with(
        model=model, messages=messages, temperature=0.7, max_tokens=100, top_p=1.0, tools=tools, tool_choice="auto"
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}

