from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai_structured import OpenAIStructuredLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai_structured.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def _mock_parse(mock_client, content="ok"):
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=content))]
    mock_client.beta.chat.completions.parse.return_value = mock_response


def test_reasoning_model_drops_temperature(mock_openai_client):
    """Reasoning models reject `temperature`; structured output must not send it."""
    config = OpenAIConfig(model="o3-mini", reasoning_effort="low")
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert "temperature" not in call_kwargs  # reasoning models don't accept temperature
    assert "max_tokens" not in call_kwargs  # also dropped for reasoning models
    assert "top_p" not in call_kwargs  # also dropped for reasoning models
    assert call_kwargs["reasoning_effort"] == "low"
    assert call_kwargs["model"] == "o3-mini"


def test_regular_model_sends_sampling_params(mock_openai_client):
    """Regular models still receive the standard sampling params."""
    config = OpenAIConfig(model="gpt-4o", temperature=0.3)
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert call_kwargs["temperature"] == 0.3
    assert "max_tokens" in call_kwargs  # standard sampling params still forwarded
    assert "top_p" in call_kwargs
    assert call_kwargs["model"] == "gpt-4o"


def test_generate_response_with_tools(mock_openai_client):
    """Tool calls must be returned, not dropped (#6420)."""
    config = OpenAIConfig(model="gpt-4o")
    llm = OpenAIStructuredLLM(config)

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "sunny day"}'

    mock_message = Mock()
    mock_message.content = "I've added the memory."
    mock_message.tool_calls = [mock_tool_call]

    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    tools = [{"type": "function", "function": {"name": "add_memory"}}]
    response = llm.generate_response([{"role": "user", "content": "Remember sunny day"}], tools=tools)

    assert response["content"] == "I've added the memory."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "sunny day"}


def test_generate_response_with_tools_no_tool_calls(mock_openai_client):
    """With tools passed but none called, the dict shape is still returned."""
    config = OpenAIConfig(model="gpt-4o")
    llm = OpenAIStructuredLLM(config)

    mock_message = Mock()
    mock_message.content = "No tools needed."
    mock_message.tool_calls = None

    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    tools = [{"type": "function", "function": {"name": "add_memory"}}]
    response = llm.generate_response([{"role": "user", "content": "Hello"}], tools=tools)

    assert response["content"] == "No tools needed."
    assert response["tool_calls"] == []


def test_generate_response_without_tools_returns_content(mock_openai_client):
    """Without tools the return value stays a plain string."""
    config = OpenAIConfig(model="gpt-4o")
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client, content="plain content")

    response = llm.generate_response([{"role": "user", "content": "Hello"}])

    assert response == "plain content"


def test_uses_openai_base_url_environment_variable(monkeypatch):
    base_url = "https://gateway.example/v1"
    monkeypatch.setenv("OPENAI_API_BASE", "https://legacy.example/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)

    with patch("mem0.llms.openai_structured.OpenAI") as mock_openai:
        OpenAIStructuredLLM(OpenAIConfig(api_key="test-api-key"))

    mock_openai.assert_called_once_with(api_key="test-api-key", base_url=base_url)
