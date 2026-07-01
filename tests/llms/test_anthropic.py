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


# --- Tool / forced structured output handling ---

OPENAI_FORMAT_TOOL = {
    "type": "function",
    "function": {
        "name": "save_memories",
        "description": "Save extracted memories.",
        "parameters": {
            "type": "object",
            "properties": {"memory": {"type": "array", "items": {"type": "object"}}},
            "required": ["memory"],
        },
    },
}


def _tool_use_block(name, payload):
    block = Mock()
    block.type = "tool_use"
    block.name = name
    block.input = payload
    return block


def test_declares_tool_call_support():
    assert AnthropicLLM.supports_tool_calls is True


def test_no_tools_path_returns_text(mock_anthropic_client):
    """Without tools, behavior is unchanged: the assistant text is returned."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)

    text_block = Mock()
    text_block.type = "text"
    text_block.text = "Hello!"
    mock_anthropic_client.messages.create.return_value = Mock(content=[text_block])

    assert llm.generate_response([{"role": "user", "content": "Hi"}]) == "Hello!"
    assert "tools" not in mock_anthropic_client.messages.create.call_args[1]


def test_openai_format_tools_converted_to_anthropic_schema(mock_anthropic_client):
    """OpenAI function-format tools are converted to Anthropic's input_schema."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    mock_anthropic_client.messages.create.return_value = Mock(
        content=[_tool_use_block("save_memories", {"memory": []})]
    )

    llm.generate_response([{"role": "user", "content": "Hi"}], tools=[OPENAI_FORMAT_TOOL], tool_choice="required")

    call_kwargs = mock_anthropic_client.messages.create.call_args[1]
    sent_tool = call_kwargs["tools"][0]
    assert sent_tool["name"] == "save_memories"
    assert "input_schema" in sent_tool and "function" not in sent_tool
    assert sent_tool["input_schema"]["required"] == ["memory"]
    # "required" maps to Anthropic's {"type": "any"}.
    assert call_kwargs["tool_choice"] == {"type": "any"}


def test_tool_use_block_parsed_into_tool_calls_dict(mock_anthropic_client):
    """A tool_use block is returned as {"content", "tool_calls"} like other providers."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    payload = {"memory": [{"id": "0", "text": "Likes hiking"}]}
    mock_anthropic_client.messages.create.return_value = Mock(content=[_tool_use_block("save_memories", payload)])

    result = llm.generate_response(
        [{"role": "user", "content": "Hi"}], tools=[OPENAI_FORMAT_TOOL], tool_choice="required"
    )

    assert result["tool_calls"] == [{"name": "save_memories", "arguments": payload}]


def test_tool_choice_auto_maps_to_dict(mock_anthropic_client):
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    mock_anthropic_client.messages.create.return_value = Mock(
        content=[_tool_use_block("save_memories", {"memory": []})]
    )

    llm.generate_response([{"role": "user", "content": "Hi"}], tools=[OPENAI_FORMAT_TOOL])

    assert mock_anthropic_client.messages.create.call_args[1]["tool_choice"] == {"type": "auto"}


def test_tool_requested_but_text_returned_yields_no_tool_calls(mock_anthropic_client):
    """If the model returns only text despite a forced tool, tool_calls is empty
    (graceful - the recovery degrades to [] rather than raising)."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    text_block = Mock()
    text_block.type = "text"
    text_block.text = "I'd rather just chat."
    mock_anthropic_client.messages.create.return_value = Mock(content=[text_block])

    result = llm.generate_response(
        [{"role": "user", "content": "Hi"}], tools=[OPENAI_FORMAT_TOOL], tool_choice="required"
    )

    assert result == {"content": "I'd rather just chat.", "tool_calls": []}


def test_already_anthropic_format_tool_passed_through(mock_anthropic_client):
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    mock_anthropic_client.messages.create.return_value = Mock(
        content=[_tool_use_block("save_memories", {"memory": []})]
    )
    native_tool = {"name": "save_memories", "description": "d", "input_schema": {"type": "object"}}

    llm.generate_response([{"role": "user", "content": "Hi"}], tools=[native_tool], tool_choice="required")

    assert mock_anthropic_client.messages.create.call_args[1]["tools"][0] == native_tool


def test_tool_missing_parameters_gets_empty_object_schema(mock_anthropic_client):
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    mock_anthropic_client.messages.create.return_value = Mock(content=[_tool_use_block("noop", {})])
    tool = {"type": "function", "function": {"name": "noop", "description": "d"}}

    llm.generate_response([{"role": "user", "content": "Hi"}], tools=[tool], tool_choice="required")

    sent_tool = mock_anthropic_client.messages.create.call_args[1]["tools"][0]
    assert sent_tool["input_schema"] == {"type": "object", "properties": {}}


def test_parse_response_output_feeds_recovery_parser(mock_anthropic_client):
    """Seam test: AnthropicLLM's tool response shape is byte-compatible with the
    recovery parser that consumes it (parse_tool_calls_for_memory)."""
    from mem0.memory.utils import parse_tool_calls_for_memory

    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)
    payload = {"memory": [{"id": "0", "text": "Likes hiking"}]}
    mock_anthropic_client.messages.create.return_value = Mock(content=[_tool_use_block("save_memories", payload)])

    response = llm.generate_response(
        [{"role": "user", "content": "Hi"}], tools=[OPENAI_FORMAT_TOOL], tool_choice="required"
    )

    assert parse_tool_calls_for_memory(response) == [{"id": "0", "text": "Likes hiking"}]


def test_no_tools_path_empty_content_returns_empty_string(mock_anthropic_client):
    """An empty content list (e.g. a blocked/refused response) must not raise
    IndexError on the no-tools path; it degrades to an empty string."""
    config = AnthropicConfig(model="claude-3-5-sonnet-20240620", api_key="test-key")
    llm = AnthropicLLM(config)

    mock_anthropic_client.messages.create.return_value = Mock(content=[])

    assert llm.generate_response([{"role": "user", "content": "Hi"}]) == ""
