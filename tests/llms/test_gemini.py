from unittest.mock import Mock, patch

import pytest
from google.genai import types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.gemini import GeminiLLM


@pytest.fixture
def mock_gemini_client():
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        mock_client = Mock()
        mock_client_class.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-2.0-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_part = Mock(text="I'm doing well, thank you for asking!")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])

    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages)

    # Check the actual call - system instruction is now in config
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args

    # Verify model and contents
    assert call_args.kwargs["model"] == "gemini-2.0-flash-latest"
    assert len(call_args.kwargs["contents"]) == 1  # Only user message

    # Verify config has system instruction
    config_arg = call_args.kwargs["config"]
    assert config_arg.system_instruction == "You are a helpful assistant."
    assert config_arg.temperature == 0.7
    assert config_arg.max_output_tokens == 100
    assert config_arg.top_p == 1.0

    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_gemini_client: Mock):
    config = BaseLlmConfig(model="gemini-1.5-flash-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)
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

    mock_tool_call = Mock()
    mock_tool_call.name = "add_memory"
    mock_tool_call.args = {"data": "Today is a sunny day."}

    # Create mock parts with both text and function_call
    mock_text_part = Mock()
    mock_text_part.text = "I've added the memory for you."
    mock_text_part.function_call = None

    mock_func_part = Mock()
    mock_func_part.text = None
    mock_func_part.function_call = mock_tool_call

    mock_content = Mock()
    mock_content.parts = [mock_text_part, mock_func_part]

    mock_candidate = Mock()
    mock_candidate.content = mock_content

    mock_response = Mock(candidates=[mock_candidate])
    mock_gemini_client.models.generate_content.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    # Check the actual call
    mock_gemini_client.models.generate_content.assert_called_once()
    call_args = mock_gemini_client.models.generate_content.call_args

    # Verify model and contents
    assert call_args.kwargs["model"] == "gemini-1.5-flash-latest"
    assert len(call_args.kwargs["contents"]) == 1  # Only user message

    # Verify config has system instruction and tools
    config_arg = call_args.kwargs["config"]
    assert config_arg.system_instruction == "You are a helpful assistant."
    assert config_arg.temperature == 0.7
    assert config_arg.max_output_tokens == 100
    assert config_arg.top_p == 1.0
    assert len(config_arg.tools) == 1
    assert config_arg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.AUTO

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_parse_response_none_content_no_tools(mock_gemini_client: Mock):
    """Gemini can return content=None when response is blocked by safety filters."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_candidate = Mock(content=None)
    mock_response = Mock(candidates=[mock_candidate])

    result = llm._parse_response(mock_response, tools=None)
    assert result == ""


def test_parse_response_none_content_with_tools(mock_gemini_client: Mock):
    """Gemini can return content=None when response is blocked by safety filters (tools path)."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_candidate = Mock(content=None)
    mock_response = Mock(candidates=[mock_candidate])

    result = llm._parse_response(mock_response, tools=[{"function": {"name": "test"}}])
    assert result == {"content": None, "tool_calls": []}


def test_parse_response_empty_candidates(mock_gemini_client: Mock):
    """Gemini can return an empty candidates list."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_response = Mock(candidates=[])
    result = llm._parse_response(mock_response, tools=None)
    assert result == ""


def test_parse_response_none_candidates(mock_gemini_client: Mock):
    """Gemini can return candidates=None."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_response = Mock(candidates=None)
    result = llm._parse_response(mock_response, tools=None)
    assert result == ""


def test_parse_response_empty_parts_no_tools(mock_gemini_client: Mock):
    """Gemini can return content with an empty parts list."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_content = Mock(parts=[])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])

    result = llm._parse_response(mock_response, tools=None)
    assert result == ""


def test_parse_response_empty_parts_with_tools(mock_gemini_client: Mock):
    """Gemini can return content with an empty parts list (tools path)."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_content = Mock(parts=[])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])

    result = llm._parse_response(mock_response, tools=[{"function": {"name": "test"}}])
    assert result == {"content": None, "tool_calls": []}


# --- Forced tool_choice + per-call kwargs (provider bug fixes) ---

_FORCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_memories",
            "description": "Save extracted memories.",
            "parameters": {"type": "object", "properties": {"memory": {"type": "array"}}, "required": ["memory"]},
        },
    }
]


def _tool_response():
    call = Mock()
    call.name = "save_memories"
    call.args = {"memory": []}
    part = Mock()
    part.text = None
    part.function_call = call
    return Mock(candidates=[Mock(content=Mock(parts=[part]))])


def test_tool_choice_required_forces_any_mode(mock_gemini_client: Mock):
    """Regression: tool_choice='required' must map to ANY (force a tool), not
    NONE (tools off). Previously 'required' fell through to NONE and silently
    disabled tool calling."""
    llm = GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", max_tokens=100))
    mock_gemini_client.models.generate_content.return_value = _tool_response()

    llm.generate_response([{"role": "user", "content": "hi"}], tools=_FORCE_TOOLS, tool_choice="required")

    cfg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY
    assert cfg.tool_config.function_calling_config.allowed_function_names == ["save_memories"]


def test_tool_choice_any_still_forces(mock_gemini_client: Mock):
    llm = GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", max_tokens=100))
    mock_gemini_client.models.generate_content.return_value = _tool_response()

    llm.generate_response([{"role": "user", "content": "hi"}], tools=_FORCE_TOOLS, tool_choice="any")

    cfg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY


def test_tool_choice_none_disables_tools(mock_gemini_client: Mock):
    llm = GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", max_tokens=100))
    mock_gemini_client.models.generate_content.return_value = _tool_response()

    llm.generate_response([{"role": "user", "content": "hi"}], tools=_FORCE_TOOLS, tool_choice="none")

    cfg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.NONE


def test_max_tokens_kwarg_overrides_config(mock_gemini_client: Mock):
    """generate_response accepts **kwargs (base-class contract); a max_tokens
    override is applied as max_output_tokens for that one call."""
    llm = GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", max_tokens=100))
    mock_part = Mock()
    mock_part.text = "ok"
    mock_part.function_call = None
    mock_gemini_client.models.generate_content.return_value = Mock(
        candidates=[Mock(content=Mock(parts=[mock_part]))]
    )

    llm.generate_response([{"role": "user", "content": "hi"}], max_tokens=8000)

    cfg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.max_output_tokens == 8000


# --- Forced-structure extraction recovery enablement (issue #3918) ---


def test_gemini_declares_tool_call_support():
    """Gemini opts into the forced-structure extraction recovery."""
    assert GeminiLLM.supports_tool_calls is True


def test_forced_structure_recovery_works_end_to_end_on_gemini(mock_gemini_client: Mock):
    """A parse failure is recovered via a forced tool call on Gemini. Exercises
    the recovery path + the forced tool_choice mapping + supports_tool_calls
    together: the model returns a structured tool call (so leaked reasoning
    tokens cannot corrupt the JSON), and the memories are recovered."""
    from mem0.memory.utils import recover_extraction_via_tools

    llm = GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", max_tokens=2000))
    call = Mock()
    call.name = "save_memories"
    call.args = {"memory": [{"id": "0", "text": "User adopted a dog named Max"}]}
    part = Mock()
    part.text = None
    part.function_call = call
    mock_gemini_client.models.generate_content.return_value = Mock(
        candidates=[Mock(content=Mock(parts=[part]))]
    )

    recovered = recover_extraction_via_tools(llm, "system prompt", "user prompt")

    assert recovered == [{"id": "0", "text": "User adopted a dog named Max"}]
    # recovery forced a tool call (ANY mode), not free text
    cfg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert cfg.tool_config.function_calling_config.mode == types.FunctionCallingConfigMode.ANY
