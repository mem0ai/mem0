from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.azure_openai import AzureOpenAILLM

MODEL = "gpt-4o"  # or your custom deployment name
TEMPERATURE = 0.7
MAX_TOKENS = 100
TOP_P = 1.0


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_openai_client):
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model=MODEL, messages=messages, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_with_tools(mock_openai_client):
    config = BaseLlmConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
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
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, tools=tools)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
        tools=tools,
        tool_choice="auto",
    )

    assert response["content"] == "I've added the memory for you."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "Today is a sunny day."}


def test_init_with_custom_http_client():
    # Test that a custom http_client is passed to AzureOpenAI

    config = BaseLlmConfig(model=MODEL)
    mock_http_client = Mock()
    config.http_client = mock_http_client
    config.azure_kwargs.api_key = "test-key"
    config.azure_kwargs.azure_deployment = "deployment"
    config.azure_kwargs.azure_endpoint = "https://endpoint"
    config.azure_kwargs.api_version = "2024-05-05"
    config.azure_kwargs.default_headers = {"x-header": "value"}

    with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai:
        AzureOpenAILLM(config)
        mock_azure_openai.assert_called_once_with(
            azure_deployment="deployment",
            azure_endpoint="https://endpoint",
            azure_ad_token_provider=None,
            api_version="2024-05-05",
            api_key="test-key",
            http_client=mock_http_client,
            default_headers={"x-header": "value"},
        )


def test_init_with_api_key(monkeypatch):
    # Patch environment variables to None to force config usage
    monkeypatch.delenv("LLM_AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_AZURE_DEPLOYMENT", raising=False)
    monkeypatch.delenv("LLM_AZURE_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_AZURE_API_VERSION", raising=False)

    config = BaseLlmConfig(
        model=MODEL,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    # Set Azure kwargs directly
    config.azure_kwargs.api_key = "test-key"
    config.azure_kwargs.azure_deployment = "test-deployment"
    config.azure_kwargs.azure_endpoint = "https://test-endpoint"
    config.azure_kwargs.api_version = "2024-01-01"
    config.azure_kwargs.default_headers = {"x-test": "header"}
    config.http_client = None

    with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai:
        llm = AzureOpenAILLM(config)
        mock_azure_openai.assert_called_once_with(
            azure_deployment="test-deployment",
            azure_endpoint="https://test-endpoint",
            azure_ad_token_provider=None,
            api_version="2024-01-01",
            api_key="test-key",
            http_client=None,
            default_headers={"x-test": "header"},
        )
        assert llm.config.model == MODEL


def test_init_with_env_vars(monkeypatch):
    monkeypatch.setenv("LLM_AZURE_OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("LLM_AZURE_DEPLOYMENT", "env-deployment")
    monkeypatch.setenv("LLM_AZURE_ENDPOINT", "https://env-endpoint")
    monkeypatch.setenv("LLM_AZURE_API_VERSION", "2024-02-02")

    config = BaseLlmConfig(model=None)
    config.azure_kwargs.api_key = None
    config.azure_kwargs.azure_deployment = None
    config.azure_kwargs.azure_endpoint = None
    config.azure_kwargs.api_version = None
    config.azure_kwargs.default_headers = None
    config.http_client = None

    with patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai:
        llm = AzureOpenAILLM(config)
        mock_azure_openai.assert_called_once_with(
            azure_deployment="env-deployment",
            azure_endpoint="https://env-endpoint",
            azure_ad_token_provider=None,
            api_version="2024-02-02",
            api_key="env-key",
            http_client=None,
            default_headers=None,
        )
        # Should default to "gpt-4o" if model is None
        assert llm.config.model == "gpt-4o"


def test_init_with_default_azure_credential(monkeypatch):
    # No API key in config or env, triggers DefaultAzureCredential
    monkeypatch.delenv("LLM_AZURE_OPENAI_API_KEY", raising=False)
    config = BaseLlmConfig(model=MODEL)
    config.azure_kwargs.api_key = None
    config.azure_kwargs.azure_deployment = "dep"
    config.azure_kwargs.azure_endpoint = "https://endpoint"
    config.azure_kwargs.api_version = "2024-03-03"
    config.azure_kwargs.default_headers = None
    config.http_client = None

    with (
        patch("mem0.llms.azure_openai.DefaultAzureCredential") as mock_cred,
        patch("mem0.llms.azure_openai.get_bearer_token_provider") as mock_token_provider,
        patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai,
    ):
        mock_cred_instance = mock_cred.return_value
        mock_token_provider.return_value = "token-provider"
        AzureOpenAILLM(config)
        mock_cred.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_cred_instance, "https://cognitiveservices.azure.com/.default")
        mock_azure_openai.assert_called_once_with(
            azure_deployment="dep",
            azure_endpoint="https://endpoint",
            azure_ad_token_provider="token-provider",
            api_version="2024-03-03",
            api_key=None,
            http_client=None,
            default_headers=None,
        )


def test_init_with_placeholder_api_key(monkeypatch):
    # Placeholder API key should trigger DefaultAzureCredential
    config = BaseLlmConfig(model=MODEL)
    config.azure_kwargs.api_key = "your-api-key"
    config.azure_kwargs.azure_deployment = "dep"
    config.azure_kwargs.azure_endpoint = "https://endpoint"
    config.azure_kwargs.api_version = "2024-04-04"
    config.azure_kwargs.default_headers = None
    config.http_client = None

    with (
        patch("mem0.llms.azure_openai.DefaultAzureCredential") as mock_cred,
        patch("mem0.llms.azure_openai.get_bearer_token_provider") as mock_token_provider,
        patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai,
    ):
        mock_cred_instance = mock_cred.return_value
        mock_token_provider.return_value = "token-provider"
        AzureOpenAILLM(config)
        mock_cred.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_cred_instance, "https://cognitiveservices.azure.com/.default")
        mock_azure_openai.assert_called_once_with(
            azure_deployment="dep",
            azure_endpoint="https://endpoint",
            azure_ad_token_provider="token-provider",
            api_version="2024-04-04",
            api_key=None,
            http_client=None,
            default_headers=None,
        )
