from unittest import mock

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
    assert llm.config.model == "gpt-4o-2024-08-06"
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
        assert llm.config.model == "gpt-4o-2024-08-06"
        mock_credential.assert_called_once()
        mock_token_provider.assert_called_once_with(mock_credential.return_value, SCOPE)
        mock_azure_openai.assert_called_once()
        args, kwargs = mock_azure_openai.call_args
        assert kwargs["api_key"] is None
        assert kwargs["azure_ad_token_provider"] == "token-provider"
