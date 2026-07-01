from unittest.mock import Mock, patch

import pytest
from google.genai import types

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.gemini import GeminiConfig
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


def test_none_config_values_omitted_from_generation_config(mock_gemini_client: Mock):
    """When temperature/max_tokens/top_p are None, they must not be passed
    to GenerateContentConfig (verified via model_fields_set)."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=None, max_tokens=None, top_p=None)
    llm = GeminiLLM(config)

    mock_part = Mock(text="ok")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])
    mock_gemini_client.models.generate_content.return_value = mock_response

    llm.generate_response([{"role": "user", "content": "hi"}])

    config_arg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert "temperature" not in config_arg.model_fields_set
    assert "max_output_tokens" not in config_arg.model_fields_set
    assert "top_p" not in config_arg.model_fields_set


def test_explicit_config_values_passed_to_generation_config(mock_gemini_client: Mock):
    """When temperature/max_tokens/top_p are explicitly set, they must appear."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.5, max_tokens=200, top_p=0.9)
    llm = GeminiLLM(config)

    mock_part = Mock(text="ok")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_response = Mock(candidates=[mock_candidate])
    mock_gemini_client.models.generate_content.return_value = mock_response

    llm.generate_response([{"role": "user", "content": "hi"}])

    config_arg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    assert "temperature" in config_arg.model_fields_set
    assert config_arg.temperature == 0.5
    assert "max_output_tokens" in config_arg.model_fields_set
    assert config_arg.max_output_tokens == 200
    assert "top_p" in config_arg.model_fields_set
    assert config_arg.top_p == 0.9


def _make_tool_call_response() -> Mock:
    """Build a generate_content response whose tool_calls parse cleanly."""
    mock_tool_call = Mock()
    mock_tool_call.name = "add_memory"
    mock_tool_call.args = {"data": "Today is a sunny day."}

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
    return Mock(candidates=[mock_candidate])


def _single_tool() -> list:
    return [
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


def test_generate_response_tool_choice_required_maps_to_any_and_locks_names(mock_gemini_client: Mock):
    """Regression #5430: ``tool_choice="required"`` is the standard value for
    "force a tool call". Gemini has no required mode, so we map it to ANY with
    allowed_function_names set — matching caller expectations from other
    providers. Previously, ``"required"`` fell through to the else branch and
    mapped to NONE, silently disabling tool calling."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_gemini_client.models.generate_content.return_value = _make_tool_call_response()

    llm.generate_response(
        [{"role": "user", "content": "Add a memory: Today is a sunny day."}],
        tools=_single_tool(),
        tool_choice="required",
    )

    config_arg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    fc = config_arg.tool_config.function_calling_config
    assert fc.mode == types.FunctionCallingConfigMode.ANY
    # ``required`` must restrict to the provided tool names, matching ``any``.
    assert fc.allowed_function_names == ["add_memory"]


def test_generate_response_tool_choice_any_still_maps_to_any_and_locks_names(mock_gemini_client: Mock):
    """Existing ``tool_choice="any"`` behaviour is preserved by the #5430 fix."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = GeminiLLM(config)

    mock_gemini_client.models.generate_content.return_value = _make_tool_call_response()

    llm.generate_response(
        [{"role": "user", "content": "Add a memory: Today is a sunny day."}],
        tools=_single_tool(),
        tool_choice="any",
    )

    config_arg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    fc = config_arg.tool_config.function_calling_config
    assert fc.mode == types.FunctionCallingConfigMode.ANY
    assert fc.allowed_function_names == ["add_memory"]


def test_generate_response_accepts_kwargs_max_tokens_override(mock_gemini_client: Mock):
    """Regression #5430: base ``LLMBase.generate_response`` accepts ``**kwargs``
    for per-call overrides. Gemini's signature previously omitted ``**kwargs``
    so any caller passing e.g. ``max_tokens=...`` raised TypeError."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.5, max_tokens=200, top_p=0.9)
    llm = GeminiLLM(config)

    mock_part = Mock(text="ok")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_gemini_client.models.generate_content.return_value = Mock(candidates=[mock_candidate])

    llm.generate_response([{"role": "user", "content": "hi"}], max_tokens=4096)

    config_arg = mock_gemini_client.models.generate_content.call_args.kwargs["config"]
    # Per-call override wins over the configured default.
    assert "max_output_tokens" in config_arg.model_fields_set
    assert config_arg.max_output_tokens == 4096


def test_generate_response_accepts_unknown_kwargs_without_raising(mock_gemini_client: Mock):
    """Arbitrary ``**kwargs`` must not raise — they are silently dropped,
    matching the base-class contract for provider-specific extras."""
    config = BaseLlmConfig(model="gemini-2.0-flash", temperature=0.5, max_tokens=200, top_p=0.9)
    llm = GeminiLLM(config)

    mock_part = Mock(text="ok")
    mock_content = Mock(parts=[mock_part])
    mock_candidate = Mock(content=mock_content)
    mock_gemini_client.models.generate_content.return_value = Mock(candidates=[mock_candidate])

    # Should not raise TypeError.
    llm.generate_response([{"role": "user", "content": "hi"}], some_future_param=True)


# --- Vertex AI backend initialization (issue #3990, PR #4030) ---


def test_init_default_path_uses_api_key(monkeypatch):
    """Default (non-Vertex) path stays backward compatible: client built with api_key, never vertexai."""
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "test-key")
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(GeminiConfig(model="gemini-2.0-flash"))
    mock_client_class.assert_called_once_with(api_key="test-key")


def test_init_backward_compat_with_base_config(monkeypatch):
    """A legacy BaseLlmConfig still works and uses the API-key path (no missing-attr error)."""
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    monkeypatch.setenv("GOOGLE_API_KEY", "legacy-key")
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash"))
    mock_client_class.assert_called_once_with(api_key="legacy-key")


def test_init_vertexai_via_explicit_config(monkeypatch):
    """vertexai=True in GeminiConfig routes to the Vertex AI client with project/location, no api_key."""
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(GeminiConfig(vertexai=True, project="my-project", location="europe-west1"))
    mock_client_class.assert_called_once_with(vertexai=True, project="my-project", location="europe-west1")


def test_init_vertexai_via_dict_config(monkeypatch):
    """The factory hands GeminiLLM a dict; the vertexai key still routes to the Vertex client."""
    monkeypatch.delenv("GOOGLE_GENAI_USE_VERTEXAI", raising=False)
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM({"vertexai": True, "project": "p", "location": "us-central1"})
    mock_client_class.assert_called_once_with(vertexai=True, project="p", location="us-central1")


def test_init_vertexai_via_env_vars(monkeypatch):
    """GOOGLE_GENAI_USE_VERTEXAI + project/location env vars enable Vertex (the exact ask in issue #3990)."""
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "asia-south1")
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(GeminiConfig())
    mock_client_class.assert_called_once_with(vertexai=True, project="env-project", location="asia-south1")


def test_init_vertexai_location_defaults_to_us_central1(monkeypatch):
    """When Vertex is on but no location is supplied, it defaults to us-central1."""
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(GeminiConfig(project="p"))
    mock_client_class.assert_called_once_with(vertexai=True, project="p", location="us-central1")


def test_init_base_config_respects_vertexai_env(monkeypatch):
    """GOOGLE_GENAI_USE_VERTEXAI is the authoritative global switch (Google's own
    convention): a legacy BaseLlmConfig is routed to Vertex when the env var is set,
    even if it carries an api_key. This pins the precedence as intentional."""
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-west1")
    with patch("mem0.llms.gemini.genai.Client") as mock_client_class:
        GeminiLLM(BaseLlmConfig(model="gemini-2.0-flash", api_key="ignored-key"))
    mock_client_class.assert_called_once_with(vertexai=True, project="env-project", location="us-west1")
