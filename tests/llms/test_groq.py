from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.groq import GroqLLM


@pytest.fixture
def mock_groq_client():
    with patch("mem0.llms.groq.Groq") as mock_groq:
        mock_client = Mock()
        mock_groq.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_groq_client):
    config = BaseLlmConfig(model="llama3-70b-8192", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_groq_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_groq_client.chat.completions.create.assert_called_once_with(
        model="llama3-70b-8192", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_groq_client):
    config = BaseLlmConfig(model="llama3-70b-8192", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
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
    mock_groq_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_groq_client.chat.completions.create.assert_called_once_with(
        model="llama3-70b-8192",
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


@pytest.mark.parametrize("model", ["groq/compound", "groq/compound-mini"])
def test_generate_response_skips_json_mode_for_compound_models(mock_groq_client, model):
    config = BaseLlmConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [{"role": "user", "content": "Hi, I'm Alice and I love hiking."}]

    # Compound models answer JSON-mode requests with empty or non-JSON content;
    # the mock mirrors that plain-text reply. These tests pin request
    # construction (response_format omitted), not end-to-end extraction.
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Alice introduced herself and mentioned she loves hiking."))]
    mock_groq_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format={"type": "json_object"})

    _, kwargs = mock_groq_client.chat.completions.create.call_args
    assert "response_format" not in kwargs


def test_generate_response_keeps_json_mode_for_standard_model(mock_groq_client):
    config = BaseLlmConfig(model="llama-3.3-70b-versatile", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [{"role": "user", "content": "Hi, I'm Alice and I love hiking."}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"memory": ["Name is Alice", "Loves hiking"]}'))]
    mock_groq_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format={"type": "json_object"})

    _, kwargs = mock_groq_client.chat.completions.create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


def test_generate_response_keeps_non_json_response_format_for_compound_model(mock_groq_client):
    config = BaseLlmConfig(model="groq/compound", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [{"role": "user", "content": "Hi, I'm Alice and I love hiking."}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Alice loves hiking."))]
    mock_groq_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format={"type": "text"})

    _, kwargs = mock_groq_client.chat.completions.create.call_args
    assert kwargs["response_format"] == {"type": "text"}


def test_generate_response_keeps_tools_when_skipping_json_mode(mock_groq_client):
    config = BaseLlmConfig(model="groq/compound", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [{"role": "user", "content": "Add a new memory: Today is a sunny day."}]
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
    mock_message.content = "Done."
    mock_message.tool_calls = None
    mock_response.choices = [Mock(message=mock_message)]
    mock_groq_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format={"type": "json_object"}, tools=tools)

    _, kwargs = mock_groq_client.chat.completions.create.call_args
    assert "response_format" not in kwargs
    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"


def test_generate_response_handles_non_string_model(mock_groq_client):
    config = BaseLlmConfig(model={"name": "custom-model"}, temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    messages = [{"role": "user", "content": "Hi, I'm Alice and I love hiking."}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"memory": []}'))]
    mock_groq_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format={"type": "json_object"})

    _, kwargs = mock_groq_client.chat.completions.create.call_args
    assert kwargs["response_format"] == {"type": "json_object"}


@pytest.mark.parametrize(
    "model,expected",
    [
        ("llama-3.3-70b-versatile", True),
        ("openai/gpt-oss-20b", True),
        ("llama3-70b-8192", True),
        ("groq/compound", False),
        ("compound-beta", False),
        ("groq/compound-mini", False),
    ],
)
def test_supports_tool_calls_excludes_compound_models(mock_groq_client, model, expected):
    # Forced-tool_choice recovery must be enabled for tool-capable Groq models
    # (#4054's provider) but NOT for the compound agentic systems, which reject
    # tool calling the same way they reject JSON response_format.
    config = BaseLlmConfig(model=model, temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GroqLLM(config)
    assert llm.supports_tool_calls is expected
