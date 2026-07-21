from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.configs import LlmConfig
from mem0.llms.mistral import MistralLLM
from mem0.utils.factory import LlmFactory


@pytest.fixture
def mock_mistral_client():
    with patch("mem0.llms.mistral.Mistral") as mock_mistral:
        mock_client = Mock()
        mock_mistral.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_mistral_client):
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages)

    mock_mistral_client.chat.complete.assert_called_once_with(
        model="mistral-small-latest", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_forwards_extra_kwargs(mock_mistral_client):
    """Per the LLMBase contract, extra provider-specific kwargs must be accepted and
    forwarded to the Mistral client (matching together/langchain/sarvam behavior)."""
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages, frequency_penalty=0.5)

    assert response == "Hi"
    call_kwargs = mock_mistral_client.chat.complete.call_args.kwargs
    assert call_kwargs["frequency_penalty"] == 0.5


def test_generate_response_with_tools(mock_mistral_client):
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
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
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_mistral_client.chat.complete.assert_called_once_with(
        model="mistral-small-latest",
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


def test_generate_response_with_tools_already_parsed_arguments(mock_mistral_client):
    # The official mistralai SDK types FunctionCall.arguments as
    # Union[Dict[str, Any], str] -- verify the already-a-dict case doesn't
    # crash json.loads().
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "Add a new memory: Today is a sunny day."}]
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

    mock_response = Mock()
    mock_message = Mock()
    mock_message.content = "I've added the memory for you."

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = {"data": "Today is a sunny day."}

    mock_message.tool_calls = [mock_tool_call]
    mock_response.choices = [Mock(message=mock_message)]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_generate_response_with_response_format(mock_mistral_client):
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "Return JSON."}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"key": "value"}'))]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages, response_format=response_format)

    mock_mistral_client.chat.complete.assert_called_once_with(
        model="mistral-small-latest",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format=response_format,
    )
    assert response == '{"key": "value"}'


def test_generate_response_with_reasoning_effort(mock_mistral_client):
    config = BaseLlmConfig(
        model="mistral-medium-3-5", temperature=0.7, max_tokens=100, top_p=1.0, reasoning_effort="high"
    )
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "Solve this step by step."}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Reasoned answer."))]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages)

    mock_mistral_client.chat.complete.assert_called_once_with(
        model="mistral-medium-3-5",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        reasoning_effort="high",
    )
    assert response == "Reasoned answer."


def test_generate_response_with_reasoning_returns_chunk_list_as_plain_text(mock_mistral_client):
    # message.content becomes a chunk list under reasoning_effort; must collapse to text only
    config = BaseLlmConfig(
        model="mistral-medium-3-5", temperature=0.7, max_tokens=100, top_p=1.0, reasoning_effort="high"
    )
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "What is 17 * 23?"}]

    think_chunk = Mock(type="thinking", thinking=[Mock(type="text", text="Let me work through this...")])
    text_chunk = Mock(type="text", text="391")

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=[think_chunk, text_chunk]))]
    mock_mistral_client.chat.complete.return_value = mock_response

    response = llm.generate_response(messages)

    assert response == "391"


def test_generate_response_without_reasoning_effort_omits_param(mock_mistral_client):
    config = BaseLlmConfig(model="mistral-small-latest", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = MistralLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi there"))]
    mock_mistral_client.chat.complete.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_mistral_client.chat.complete.call_args.kwargs
    assert "reasoning_effort" not in call_kwargs


def test_mistral_llm_default_model(mock_mistral_client):
    config = BaseLlmConfig(api_key="test-key")
    llm = MistralLLM(config)
    assert llm.config.model == "mistral-small-latest"


def test_mistral_llm_env_api_key(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "env-api-key")
    with patch("mem0.llms.mistral.Mistral") as mock_mistral_class:
        config = BaseLlmConfig(model="mistral-small-latest")
        MistralLLM(config)
        mock_mistral_class.assert_called_once_with(api_key="env-api-key")


def test_factory_creates_mistral_llm(mock_mistral_client):
    llm = LlmFactory.create("mistral", {"model": "mistral-small-latest", "api_key": "test-key"})
    assert isinstance(llm, MistralLLM)
    assert llm.config.model == "mistral-small-latest"


def test_mistral_accepts_base_llm_config():
    config = LlmConfig(provider="mistral", config={"model": "mistral-small-latest"})
    assert config.provider == "mistral"
