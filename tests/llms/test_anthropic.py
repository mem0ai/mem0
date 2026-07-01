from unittest.mock import Mock, patch

import pytest


pytest.importorskip("anthropic", reason="anthropic package not installed")

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.base import BaseLlmConfig

from mem0.llms.anthropic import AnthropicLLM


@pytest.fixture
def mock_anthropic_client():

    with patch("mem0.llms.anthropic.anthropic") as mock_anthropic:
        mock_client = Mock()
        mock_anthropic.Anthropic.return_value = mock_client
        yield mock_client


def test_default_config_omits_top_p(mock_anthropic_client):
    """Default AnthropicConfig should not set top_p to avoid conflict with temperature."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    assert config.top_p is None
    assert config.temperature == 0.1


def test_generate_response_does_not_send_top_p_by_default(mock_anthropic_client):
    """Anthropic API rejects temperature and top_p together; top_p must be omitted by default."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)

    mock_response = Mock()
    mock_response.content = [Mock(text="Hello!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi"},
    ]

    llm.generate_response(messages)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert "top_p" not in call_kwargs
    assert call_kwargs["temperature"] == 0.1


def test_generate_response_sends_top_p_alone_when_no_temperature(mock_anthropic_client):
    """When user sets only top_p (no temperature), top_p should be sent."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key", top_p=0.9, temperature=None)
    llm = AnthropicLLM(config)

    mock_response = Mock()
    mock_response.content = [Mock(text="Hello!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi"},
    ]

    llm.generate_response(messages)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["top_p"] == 0.9
    assert "temperature" not in call_kwargs


def test_both_set_prefers_temperature_over_top_p(mock_anthropic_client):
    """When both temperature and top_p are set, temperature wins and top_p is dropped."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key", top_p=0.9, temperature=0.5)
    llm = AnthropicLLM(config)

    mock_response = Mock()
    mock_response.content = [Mock(text="Hello!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    messages = [{"role": "user", "content": "Hi"}]
    llm.generate_response(messages)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert call_kwargs["temperature"] == 0.5
    assert "top_p" not in call_kwargs


def test_configured_base_url_is_passed_to_client():
    """A configured anthropic_base_url must reach the Anthropic client constructor."""
    with patch("mem0.llms.anthropic.anthropic") as mock_anthropic:
        config = AnthropicConfig(
            model="claude-3-5-sonnet-20240620",
            api_key="test-key",
            anthropic_base_url="https://proxy.example.com",
        )
        AnthropicLLM(config)

    assert mock_anthropic.Anthropic.call_args[1]["base_url"] == "https://proxy.example.com"


def test_base_url_falls_back_to_env(monkeypatch):
    """When no base_url is configured, ANTHROPIC_BASE_URL is used."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "https://env.example.com")
    with patch("mem0.llms.anthropic.anthropic") as mock_anthropic:
        config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
        AnthropicLLM(config)

    assert mock_anthropic.Anthropic.call_args[1]["base_url"] == "https://env.example.com"


def test_base_url_omitted_when_unset(monkeypatch):
    """With no base_url anywhere, base_url must not be forced to None on the client."""
    monkeypatch.delenv("ANTHROPIC_BASE_URL", raising=False)
    with patch("mem0.llms.anthropic.anthropic") as mock_anthropic:
        config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
        AnthropicLLM(config)

    assert "base_url" not in mock_anthropic.Anthropic.call_args[1]


def test_base_config_conversion_does_not_send_both(mock_anthropic_client):
    """BaseLlmConfig defaults both temperature=0.1 and top_p=0.1; Anthropic must not send both."""
    base_config = BaseLlmConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(base_config)

    mock_response = Mock()
    mock_response.content = [Mock(text="Hello!")]
    mock_anthropic_client.messages.create.return_value = mock_response

    messages = [{"role": "user", "content": "Hi"}]
    llm.generate_response(messages)

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    assert "temperature" in call_kwargs
    assert "top_p" not in call_kwargs
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
