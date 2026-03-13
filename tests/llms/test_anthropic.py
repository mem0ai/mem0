from unittest.mock import Mock, patch

import pytest

pytest.importorskip("anthropic", reason="anthropic package not installed")

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.anthropic import AnthropicLLM


@pytest.fixture
def mock_anthropic_client():
    with patch("mem0.llms.anthropic.anthropic") as mock_module:
        mock_client = Mock()
        mock_module.Anthropic.return_value = mock_client
        yield mock_client, mock_module


def _make_text_response(text):
    """Create a mock Anthropic Message with a single TextBlock."""
    text_block = Mock()
    text_block.type = "text"
    text_block.text = text
    response = Mock()
    response.content = [text_block]
    response.stop_reason = "end_turn"
    return response


def _make_tool_response(tool_name, tool_input, tool_id="toolu_123", text=None):
    """Create a mock Anthropic Message with a ToolUseBlock (and optional TextBlock)."""
    blocks = []
    if text:
        text_block = Mock()
        text_block.type = "text"
        text_block.text = text
        blocks.append(text_block)

    tool_block = Mock()
    tool_block.type = "tool_use"
    tool_block.id = tool_id
    tool_block.name = tool_name
    tool_block.input = tool_input
    blocks.append(tool_block)

    response = Mock()
    response.content = blocks
    response.stop_reason = "tool_use"
    return response


# --- Config & Init Tests ---


def test_default_model_is_current(mock_anthropic_client):
    """Default model should be a reasonably current Claude model, not the old 2024 one."""
    config = AnthropicConfig(api_key="test-key")
    llm = AnthropicLLM(config)
    assert "claude-3-5-sonnet-20240620" not in llm.config.model
    assert "claude" in llm.config.model


def test_api_key_from_config(mock_anthropic_client):
    _, mock_module = mock_anthropic_client
    config = AnthropicConfig(api_key="sk-test-123")
    AnthropicLLM(config)
    mock_module.Anthropic.assert_called_once()
    call_kwargs = mock_module.Anthropic.call_args
    assert call_kwargs.kwargs.get("api_key") == "sk-test-123" or call_kwargs[1].get("api_key") == "sk-test-123"


def test_base_url_passed_to_client(mock_anthropic_client):
    """When anthropic_base_url is set in config, it should be passed to the Anthropic client."""
    _, mock_module = mock_anthropic_client
    config = AnthropicConfig(api_key="test-key", anthropic_base_url="https://custom.api.example.com")
    AnthropicLLM(config)
    call_kwargs = mock_module.Anthropic.call_args
    # base_url should be forwarded to the client constructor
    assert call_kwargs.kwargs.get("base_url") == "https://custom.api.example.com" or \
        call_kwargs[1].get("base_url") == "https://custom.api.example.com"


def test_base_url_not_passed_when_none(mock_anthropic_client):
    """When anthropic_base_url is None, base_url should not be set on the client."""
    _, mock_module = mock_anthropic_client
    config = AnthropicConfig(api_key="test-key")
    AnthropicLLM(config)
    call_kwargs = mock_module.Anthropic.call_args
    # Should NOT have base_url, or it should be None
    base_url = call_kwargs.kwargs.get("base_url") or (call_kwargs[1].get("base_url") if len(call_kwargs) > 1 else None)
    assert base_url is None


# --- generate_response Tests ---


def test_generate_response_without_tools(mock_anthropic_client):
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key",
                             temperature=0.7, max_tokens=100, top_p=1.0)
    llm = AnthropicLLM(config)

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_client.messages.create.return_value = _make_text_response("I'm doing well!")

    response = llm.generate_response(messages)

    # System message should be separated out
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "You are a helpful assistant."
    assert call_kwargs["messages"] == [{"role": "user", "content": "Hello, how are you?"}]
    assert call_kwargs["model"] == "claude-sonnet-4-20250514"

    assert response == "I'm doing well!"


def test_system_message_separation(mock_anthropic_client):
    """System messages must be extracted and passed as the `system` parameter."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(config)

    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "What is 2+2?"},
        {"role": "assistant", "content": "4"},
        {"role": "user", "content": "And 3+3?"},
    ]

    mock_client.messages.create.return_value = _make_text_response("6")
    llm.generate_response(messages)

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["system"] == "Be concise."
    # filtered_messages should not contain system message
    assert all(m["role"] != "system" for m in call_kwargs["messages"])
    assert len(call_kwargs["messages"]) == 3


def test_generate_response_with_tools(mock_anthropic_client):
    """When tools are provided and model uses one, response should match OpenAI connector format."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(config)

    messages = [
        {"role": "user", "content": "Add a memory: Today is sunny."},
    ]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "add_memory",
                "description": "Add a memory",
                "parameters": {
                    "type": "object",
                    "properties": {"data": {"type": "string"}},
                    "required": ["data"],
                },
            },
        }
    ]

    mock_client.messages.create.return_value = _make_tool_response(
        tool_name="add_memory",
        tool_input={"data": "Today is sunny."},
        text="I'll add that memory.",
    )

    response = llm.generate_response(messages, tools=tools)

    # Should return structured dict matching OpenAI connector format
    assert isinstance(response, dict)
    assert response["content"] == "I'll add that memory."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is sunny."}


def test_generate_response_tools_no_text_block(mock_anthropic_client):
    """When tool response has no text block, content should be empty string."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(config)

    messages = [{"role": "user", "content": "Do the thing."}]
    tools = [{"type": "function", "function": {"name": "do_thing", "description": "Do it", "parameters": {"type": "object", "properties": {}}}}]

    # Tool response with NO text block — only tool_use
    mock_client.messages.create.return_value = _make_tool_response(
        tool_name="do_thing",
        tool_input={},
        text=None,  # no text block
    )

    response = llm.generate_response(messages, tools=tools)

    assert isinstance(response, dict)
    assert response["content"] == ""
    assert len(response["tool_calls"]) == 1


def test_generate_response_tools_provided_but_not_used(mock_anthropic_client):
    """When tools are provided but model doesn't use them, return plain text."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(config)

    messages = [{"role": "user", "content": "Just say hello."}]
    tools = [{"type": "function", "function": {"name": "add_memory", "description": "Add a memory", "parameters": {"type": "object", "properties": {}}}}]

    # Model returns text, no tool use
    mock_client.messages.create.return_value = _make_text_response("Hello!")

    response = llm.generate_response(messages, tools=tools)

    # Should return structured response with empty tool_calls
    assert isinstance(response, dict)
    assert response["content"] == "Hello!"
    assert response["tool_calls"] == []


# --- Temperature / top_p mutual exclusion tests (upstream #4471) ---


def test_default_config_omits_top_p(mock_anthropic_client):
    """Default AnthropicConfig should not set top_p to avoid conflict with temperature."""
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    assert config.top_p is None
    assert config.temperature == 0.1


def test_generate_response_does_not_send_top_p_by_default(mock_anthropic_client):
    """Anthropic API rejects temperature and top_p together; top_p must be omitted by default."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(config)

    mock_client.messages.create.return_value = _make_text_response("Hello!")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi"},
    ]

    llm.generate_response(messages)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert "top_p" not in call_kwargs
    assert call_kwargs["temperature"] == 0.1


def test_generate_response_sends_top_p_alone_when_no_temperature(mock_anthropic_client):
    """When user sets only top_p (no temperature), top_p should be sent."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", top_p=0.9, temperature=None)
    llm = AnthropicLLM(config)

    mock_client.messages.create.return_value = _make_text_response("Hello!")

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hi"},
    ]

    llm.generate_response(messages)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["top_p"] == 0.9
    assert "temperature" not in call_kwargs


def test_both_set_prefers_temperature_over_top_p(mock_anthropic_client):
    """When both temperature and top_p are set, temperature wins and top_p is dropped."""
    mock_client, _ = mock_anthropic_client
    config = AnthropicConfig(model="claude-sonnet-4-20250514", api_key="test-key", top_p=0.9, temperature=0.5)
    llm = AnthropicLLM(config)

    mock_client.messages.create.return_value = _make_text_response("Hello!")

    messages = [{"role": "user", "content": "Hi"}]
    llm.generate_response(messages)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert call_kwargs["temperature"] == 0.5
    assert "top_p" not in call_kwargs


def test_base_config_conversion_does_not_send_both(mock_anthropic_client):
    """BaseLlmConfig defaults both temperature=0.1 and top_p=0.1; Anthropic must not send both."""
    mock_client, _ = mock_anthropic_client
    base_config = BaseLlmConfig(model="claude-sonnet-4-20250514", api_key="test-key")
    llm = AnthropicLLM(base_config)

    mock_client.messages.create.return_value = _make_text_response("Hello!")

    messages = [{"role": "user", "content": "Hi"}]
    llm.generate_response(messages)

    call_kwargs = mock_client.messages.create.call_args[1]
    assert "temperature" in call_kwargs
    assert "top_p" not in call_kwargs
