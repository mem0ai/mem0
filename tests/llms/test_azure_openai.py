from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.azure import AzureOpenAIConfig
from mem0.llms.azure_openai import AzureOpenAILLM

MODEL = "gpt-4.1-nano-2025-04-14"  # or your custom deployment name
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
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
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
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
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


def test_generate_response_with_response_format(mock_openai_client):
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a memory extraction assistant."},
        {"role": "user", "content": "I like hiking on weekends."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"facts": ["User likes hiking on weekends"]}'))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, response_format={"type": "json_object"})

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model=MODEL,
        messages=messages,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
        response_format={"type": "json_object"},
    )
    assert response == '{"facts": ["User likes hiking on weekends"]}'


def test_generate_response_without_response_format(mock_openai_client):
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a joke."},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Why did the chicken cross the road?"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert "response_format" not in call_kwargs
    assert response == "Why did the chicken cross the road?"


def test_generate_response_does_not_mutate_caller_messages(mock_openai_client):
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [{"role": "user", "content": "my assistant helps me schedule meetings"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    assert messages[-1]["content"] == "my assistant helps me schedule meetings"


def test_generate_response_rewrites_assistant_keyword_for_model_only(mock_openai_client):
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [{"role": "user", "content": "my assistant helps me"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    sent_messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
    assert sent_messages[-1]["content"] == "my ai helps me"
    assert messages[-1]["content"] == "my assistant helps me"


def test_generate_response_handles_multimodal_content(mock_openai_client):
    config = AzureOpenAIConfig(model=MODEL, temperature=TEMPERATURE, max_tokens=MAX_TOKENS, top_p=TOP_P)
    llm = AzureOpenAILLM(config)
    messages = [{"role": "user", "content": [{"type": "text", "text": "describe my assistant"}]}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    assert response == "ok"
    sent_messages = mock_openai_client.chat.completions.create.call_args[1]["messages"]
    assert sent_messages[-1]["content"] == [{"type": "text", "text": "describe my assistant"}]


def test_reasoning_model_with_reasoning_effort(mock_openai_client):
    """Test that reasoning_effort is passed to the API for Azure reasoning models."""
    config = AzureOpenAIConfig(model="o3-mini", reasoning_effort="low")
    llm = AzureOpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful ai."},
        {"role": "user", "content": "Hello"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response from o3-mini"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert call_kwargs[1]["reasoning_effort"] == "low"
    assert "temperature" not in call_kwargs[1]
    assert response == "Response from o3-mini"


def test_azure_reasoning_effort_not_passed_when_none(mock_openai_client):
    """Test that reasoning_effort is not passed when not configured on Azure."""
    config = AzureOpenAIConfig(model="o3-mini")
    llm = AzureOpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful ai."},
        {"role": "user", "content": "Hello"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args
    assert "reasoning_effort" not in call_kwargs[1]


def test_azure_config_accepts_reasoning_effort():
    """Test that AzureOpenAIConfig accepts reasoning_effort without TypeError (issue #3651)."""
    config = AzureOpenAIConfig(
        model="o3-mini",
        reasoning_effort="low",
        azure_kwargs={"api_key": "test"},
    )
    assert config.reasoning_effort == "low"
    assert config.model == "o3-mini"


def test_is_reasoning_model_override_forces_reasoning_path(mock_openai_client):
    """Versioned Azure gpt-5.x deployments can opt in via is_reasoning_model=True.

    Regression test for https://github.com/mem0ai/mem0/issues/5296 — the
    name-based heuristic does not recognize dated deployment names like
    ``gpt-5.4-nano-2026-03-17``, so the call sent max_tokens and Azure replied
    400. The explicit override forces the reasoning-model parameter set, which
    drops max_tokens (and temperature).
    """
    config = AzureOpenAIConfig(
        model="gpt-5.4-nano-2026-03-17",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        is_reasoning_model=True,
    )
    llm = AzureOpenAILLM(config)
    messages = [{"role": "user", "content": "I have oily skin."}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert "max_tokens" not in call_kwargs
    assert "temperature" not in call_kwargs


def test_is_reasoning_model_override_false_keeps_standard_params(mock_openai_client):
    """is_reasoning_model=False forces the standard param set even for o-series names."""
    config = AzureOpenAIConfig(
        model="o3-mini",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
        is_reasoning_model=False,
    )
    llm = AzureOpenAILLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_openai_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.chat.completions.create.call_args[1]
    assert call_kwargs["max_tokens"] == MAX_TOKENS
    assert call_kwargs["temperature"] == TEMPERATURE


def test_is_reasoning_model_defaults_to_name_heuristic(mock_openai_client):
    """When is_reasoning_model is None (default), classification stays name-based."""
    config = AzureOpenAIConfig(
        model="gpt-5.4-nano-2026-03-17",
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        top_p=TOP_P,
    )
    llm = AzureOpenAILLM(config)
    # Unrecognized versioned name -> heuristic says "not reasoning" (unchanged).
    assert config.is_reasoning_model is None
    assert llm._is_reasoning_model("gpt-5.4-nano-2026-03-17") is False


@pytest.mark.parametrize(
    "default_headers",
    [None, {"Firstkey": "FirstVal", "SecondKey": "SecondVal"}],
)
def test_generate_with_http_proxies(default_headers):
    mock_http_client = Mock()
    mock_http_client_instance = Mock()
    mock_http_client.return_value = mock_http_client_instance
    azure_kwargs = {"api_key": "test"}
    if default_headers:
        azure_kwargs["default_headers"] = default_headers

    with (
        patch("mem0.llms.azure_openai.AzureOpenAI") as mock_azure_openai,
        patch("httpx.Client", new=mock_http_client),
    ):
        config = AzureOpenAIConfig(
            model=MODEL,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            top_p=TOP_P,
            api_key="test",
            http_client_proxies="http://testproxy.mem0.net:8000",
            azure_kwargs=azure_kwargs,
        )

        _ = AzureOpenAILLM(config)

        mock_azure_openai.assert_called_once_with(
            api_key="test",
            http_client=mock_http_client_instance,
            azure_deployment=None,
            azure_endpoint=None,
            azure_ad_token_provider=None,
            api_version=None,
            default_headers=default_headers,
        )
        mock_http_client.assert_called_once_with(proxy="http://testproxy.mem0.net:8000")


def test_init_with_api_key(monkeypatch):
    # Patch environment variables to None to force config usage
    monkeypatch.delenv("LLM_AZURE_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_AZURE_DEPLOYMENT", raising=False)
    monkeypatch.delenv("LLM_AZURE_ENDPOINT", raising=False)
    monkeypatch.delenv("LLM_AZURE_API_VERSION", raising=False)

    config = AzureOpenAIConfig(
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

    config = AzureOpenAIConfig(model=None)
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
        # Should default to "gpt-5-mini" if model is None
        assert llm.config.model == "gpt-5-mini"


def test_init_with_default_azure_credential(monkeypatch):
    # No API key in config or env, triggers DefaultAzureCredential
    monkeypatch.delenv("LLM_AZURE_OPENAI_API_KEY", raising=False)
    config = AzureOpenAIConfig(model=MODEL)
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
    config = AzureOpenAIConfig(model=MODEL)
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
