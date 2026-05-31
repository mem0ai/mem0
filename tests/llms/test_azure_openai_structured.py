from unittest import mock
from unittest.mock import Mock

from mem0.llms.azure_openai_structured import SCOPE, AzureOpenAIStructuredLLM


class DummyAzureKwargs:
    def __init__(
        self,
        api_key=None,
        azure_deployment="test-deployment",
        azure_endpoint="https://test-endpoint.openai.azure.com",
        api_version="2024-06-01-preview",
        default_headers=None,
    ):
        self.api_key = api_key
        self.azure_deployment = azure_deployment
        self.azure_endpoint = azure_endpoint
        self.api_version = api_version
        self.default_headers = default_headers


class DummyConfig:
    def __init__(
        self,
        model=None,
        azure_kwargs=None,
        temperature=0.7,
        max_tokens=256,
        top_p=1.0,
        http_client=None,
    ):
        self.model = model
        self.azure_kwargs = azure_kwargs or DummyAzureKwargs()
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.http_client = http_client


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
def test_init_with_api_key(mock_azure_openai):
    config = DummyConfig(model="test-model", azure_kwargs=DummyAzureKwargs(api_key="real-key"))
    llm = AzureOpenAIStructuredLLM(config)
    assert llm.config.model == "test-model"
    mock_azure_openai.assert_called_once()
    args, kwargs = mock_azure_openai.call_args
    assert kwargs["api_key"] == "real-key"
    assert kwargs["azure_ad_token_provider"] is None


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
@mock.patch("mem0.llms.azure_openai_structured.get_bearer_token_provider")
@mock.patch("mem0.llms.azure_openai_structured.DefaultAzureCredential")
def test_init_with_default_credential(mock_credential, mock_token_provider, mock_azure_openai):
    config = DummyConfig(model=None, azure_kwargs=DummyAzureKwargs(api_key=None))
    mock_token_provider.return_value = "token-provider"
    llm = AzureOpenAIStructuredLLM(config)
    # Should set default model if not provided
    assert llm.config.model == "gpt-5-mini"
    mock_credential.assert_called_once()
    mock_token_provider.assert_called_once_with(mock_credential.return_value, SCOPE)
    mock_azure_openai.assert_called_once()
    args, kwargs = mock_azure_openai.call_args
    assert kwargs["api_key"] is None
    assert kwargs["azure_ad_token_provider"] == "token-provider"


def test_init_with_env_vars(monkeypatch, mocker):
    mock_azure_openai = mocker.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
    monkeypatch.setenv("LLM_AZURE_DEPLOYMENT", "test-deployment")
    monkeypatch.setenv("LLM_AZURE_ENDPOINT", "https://test-endpoint.openai.azure.com")
    monkeypatch.setenv("LLM_AZURE_API_VERSION", "2024-06-01-preview")
    config = DummyConfig(model="test-model", azure_kwargs=DummyAzureKwargs(api_key=None))
    AzureOpenAIStructuredLLM(config)
    mock_azure_openai.assert_called_once()
    args, kwargs = mock_azure_openai.call_args
    assert kwargs["api_key"] is None
    assert kwargs["azure_deployment"] == "test-deployment"
    assert kwargs["azure_endpoint"] == "https://test-endpoint.openai.azure.com"
    assert kwargs["api_version"] == "2024-06-01-preview"


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
def test_init_with_placeholder_api_key_uses_default_credential(
    mock_azure_openai,
):
    with (
        mock.patch("mem0.llms.azure_openai_structured.DefaultAzureCredential") as mock_credential,
        mock.patch("mem0.llms.azure_openai_structured.get_bearer_token_provider") as mock_token_provider,
    ):
        config = DummyConfig(model=None, azure_kwargs=DummyAzureKwargs(api_key="your-api-key"))
        mock_token_provider.return_value = "token-provider"
        llm = AzureOpenAIStructuredLLM(config)
        assert llm.config.model == "gpt-5-mini"
        mock_credential.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_credential.return_value, SCOPE)
        mock_azure_openai.assert_called_once()
        args, kwargs = mock_azure_openai.call_args
        assert kwargs["api_key"] is None
        assert kwargs["azure_ad_token_provider"] == "token-provider"


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
def test_generate_response_without_tools(mock_azure_openai):
    mock_client = Mock()
    mock_azure_openai.return_value = mock_client

    config = DummyConfig(model="test-model", azure_kwargs=DummyAzureKwargs(api_key="real-key"))
    llm = AzureOpenAIStructuredLLM(config)

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hello there!"))]
    mock_client.chat.completions.create.return_value = mock_response

    messages = [{"role": "user", "content": "Hi"}]
    response = llm.generate_response(messages)

    assert response == "Hello there!"


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
def test_generate_response_with_tools(mock_azure_openai):
    mock_client = Mock()
    mock_azure_openai.return_value = mock_client

    config = DummyConfig(model="test-model", azure_kwargs=DummyAzureKwargs(api_key="real-key"))
    llm = AzureOpenAIStructuredLLM(config)

    mock_tool_call = Mock()
    mock_tool_call.function.name = "add_memory"
    mock_tool_call.function.arguments = '{"data": "sunny day"}'

    mock_message = Mock()
    mock_message.content = "I've added the memory."
    mock_message.tool_calls = [mock_tool_call]

    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_client.chat.completions.create.return_value = mock_response

    tools = [{"type": "function", "function": {"name": "add_memory"}}]
    messages = [{"role": "user", "content": "Remember sunny day"}]
    response = llm.generate_response(messages, tools=tools)

    assert response["content"] == "I've added the memory."
    assert len(response["tool_calls"]) == 1
    assert response["tool_calls"][0]["name"] == "add_memory"
    assert response["tool_calls"][0]["arguments"] == {"data": "sunny day"}


@mock.patch("mem0.llms.azure_openai_structured.AzureOpenAI")
def test_generate_response_with_tools_no_tool_calls(mock_azure_openai):
    mock_client = Mock()
    mock_azure_openai.return_value = mock_client

    config = DummyConfig(model="test-model", azure_kwargs=DummyAzureKwargs(api_key="real-key"))
    llm = AzureOpenAIStructuredLLM(config)

    mock_message = Mock()
    mock_message.content = "No tools needed."
    mock_message.tool_calls = None

    mock_response = Mock()
    mock_response.choices = [Mock(message=mock_message)]
    mock_client.chat.completions.create.return_value = mock_response

    tools = [{"type": "function", "function": {"name": "add_memory"}}]
    messages = [{"role": "user", "content": "Hello"}]
    response = llm.generate_response(messages, tools=tools)

    assert response["content"] == "No tools needed."
    assert response["tool_calls"] == []
