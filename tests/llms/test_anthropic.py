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
