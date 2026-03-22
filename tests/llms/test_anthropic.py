from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.llms.anthropic import AnthropicLLM


@pytest.fixture
def mock_anthropic_client():
    with patch("mem0.llms.anthropic.anthropic") as mock_module:
        mock_client = Mock()
        mock_module.Anthropic.return_value = mock_client
        yield mock_client


def test_generate_response_without_response_format(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text="I'm doing well, thank you for asking!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert not any(m.get("content") == "{" for m in call_kwargs["messages"])
    assert "output_config" not in call_kwargs
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_json_object_format(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "system", "content": "Extract facts."},
        {"role": "user", "content": "My name is Alice."},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='"facts": ["Name is Alice"]}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    assert response == '{"facts": ["Name is Alice"]}'
    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["messages"][-1] == {"role": "assistant", "content": "{"}
    assert "valid JSON only" in call_kwargs["system"]


def test_generate_response_json_object_without_system_message(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [
        {"role": "user", "content": "My name is Bob."},
    ]

    mock_response = Mock()
    mock_response.content = [Mock(text='"facts": ["Name is Bob"]}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    assert response == '{"facts": ["Name is Bob"]}'
    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert "valid JSON only" in call_kwargs["system"]


def test_generate_response_json_object_strips_code_fences(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [{"role": "user", "content": "Extract facts."}]

    mock_response = Mock()
    mock_response.content = [Mock(text='"facts": []}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    assert response == '{"facts": []}'


def test_generate_response_with_json_schema_format(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [{"role": "user", "content": "Extract info."}]
    schema = {
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    }

    mock_response = Mock()
    mock_response.content = [Mock(text='{"name": "Alice"}')]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(
        messages,
        response_format={"type": "json_schema", "json_schema": {"schema": schema}},
    )

    assert response == '{"name": "Alice"}'
    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
    assert call_kwargs["output_config"]["format"]["schema"] == schema
    assert not any(isinstance(m, dict) and m.get("content") == "{" for m in call_kwargs["messages"])


def test_generate_response_with_tools(mock_anthropic_client):
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)
    messages = [{"role": "user", "content": "What is the weather?"}]
    tools = [{"name": "get_weather", "description": "Get weather", "input_schema": {"type": "object"}}]

    mock_response = Mock()
    mock_response.content = [Mock(text="It's sunny.")]
    mock_anthropic_client.messages.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools, tool_choice="any")

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["tools"] == tools
    assert call_kwargs["tool_choice"] == "any"
    assert response == "It's sunny."
