from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.n1n import N1NConfig
from mem0.llms.n1n import N1NLLM


@pytest.fixture
def mock_n1n_client():
    with patch("mem0.llms.n1n.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_n1n_initialization_with_api_key():
    """Test N1N LLM initialization with API key in config."""
    config = N1NConfig(model="gpt-4o-mini", api_key="test_n1n_api_key")
    with patch("mem0.llms.n1n.OpenAI") as mock_openai:
        llm = N1NLLM(config)
        mock_openai.assert_called_once()
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://n1n.ai/v1"
        assert call_kwargs["api_key"] == "test_n1n_api_key"


def test_n1n_initialization_with_env_var():
    """Test N1N LLM initialization with API key from environment variable."""
    config = N1NConfig(model="gpt-4o-mini")
    with patch("mem0.llms.n1n.OpenAI") as mock_openai:
        with patch("mem0.llms.n1n.os.getenv", return_value="env_n1n_api_key"):
            llm = N1NLLM(config)
            mock_openai.assert_called_once()
            call_kwargs = mock_openai.call_args[1]
            assert call_kwargs["api_key"] == "env_n1n_api_key"


def test_n1n_initialization_without_api_key():
    """Test N1N LLM initialization fails without API key."""
    config = N1NConfig(model="gpt-4o-mini")
    with patch("mem0.llms.n1n.os.getenv", return_value=None):
        with pytest.raises(ValueError, match="N1N API key is required"):
            N1NLLM(config)


def test_n1n_default_model():
    """Test N1N LLM uses default model when not specified."""
    config = N1NConfig(api_key="test_key")
    with patch("mem0.llms.n1n.OpenAI"):
        llm = N1NLLM(config)
        assert llm.config.model == "gpt-4o-mini"


def test_n1n_custom_base_url():
    """Test N1N LLM with custom base URL."""
    config = N1NConfig(model="gpt-4", api_key="test_key", n1n_base_url="https://custom.n1n.ai/v1")
    with patch("mem0.llms.n1n.OpenAI") as mock_openai:
        llm = N1NLLM(config)
        call_kwargs = mock_openai.call_args[1]
        assert call_kwargs["base_url"] == "https://custom.n1n.ai/v1"


def test_generate_response_without_tools(mock_n1n_client):
    """Test generating response without tools."""
    config = N1NConfig(model="gpt-4o-mini", api_key="test_key", temperature=0.7, max_tokens=100)
    llm = N1NLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_n1n_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_n1n_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_n1n_client.chat.completions.create.call_args[1]
    assert call_kwargs["model"] == "gpt-4o-mini"
    assert call_kwargs["messages"] == messages
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_n1n_client):
    """Test generating response with tools."""
    config = N1NConfig(model="gpt-4o-mini", api_key="test_key", temperature=0.7, max_tokens=100)
    llm = N1NLLM(config)
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
    mock_n1n_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_n1n_client.chat.completions.create.assert_called_once()
    call_kwargs = mock_n1n_client.chat.completions.create.call_args[1]
    assert call_kwargs["tools"] == tools
    assert call_kwargs["tool_choice"] == "auto"
    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"


def test_generate_response_with_response_format(mock_n1n_client):
    """Test generating response with custom response format."""
    config = N1NConfig(model="gpt-4o-mini", api_key="test_key")
    llm = N1NLLM(config)
    messages = [{"role": "user", "content": "Generate a JSON response"}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"result": "success"}'))]
    mock_n1n_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, response_format=response_format)

    call_kwargs = mock_n1n_client.chat.completions.create.call_args[1]
    assert call_kwargs["response_format"] == response_format


def test_n1n_config_conversion_from_base():
    """Test converting BaseLlmConfig to N1NConfig."""
    base_config = BaseLlmConfig(
        model="claude-3-5-sonnet-20241022",
        temperature=0.5,
        api_key="test_key",
        max_tokens=1000,
    )
    with patch("mem0.llms.n1n.OpenAI"):
        llm = N1NLLM(base_config)
        assert isinstance(llm.config, N1NConfig)
        assert llm.config.model == "claude-3-5-sonnet-20241022"
        assert llm.config.temperature == 0.5
        assert llm.config.n1n_base_url == "https://n1n.ai/v1"


def test_n1n_config_from_dict():
    """Test creating N1N LLM from dict config."""
    config_dict = {
        "model": "gemini-2.0-flash-exp",
        "api_key": "test_key",
        "temperature": 0.3,
        "n1n_base_url": "https://n1n.ai/v1",
    }
    with patch("mem0.llms.n1n.OpenAI"):
        llm = N1NLLM(config_dict)
        assert llm.config.model == "gemini-2.0-flash-exp"
        assert llm.config.temperature == 0.3


def test_n1n_multiple_models():
    """Test N1N LLM works with different model types (OpenAI, Anthropic, etc)."""
    models = ["gpt-4o-mini", "claude-3-5-sonnet-20241022", "gemini-2.0-flash-exp", "llama-3.1-70b"]
    
    for model in models:
        config = N1NConfig(model=model, api_key="test_key")
        with patch("mem0.llms.n1n.OpenAI"):
            llm = N1NLLM(config)
            assert llm.config.model == model
