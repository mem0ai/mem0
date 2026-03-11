from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.novita import NovitaConfig
from mem0.llms.novita import NovitaLLM


@pytest.fixture
def mock_novita_client():
    with patch("mem0.llms.novita.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_openai, mock_client


def test_novita_llm_uses_deepseek_default_model(mock_novita_client):
    _, _ = mock_novita_client
    llm = NovitaLLM(NovitaConfig(api_key="api_key"))
    assert llm.config.model == "deepseek/deepseek-v3.2"


def test_novita_llm_supports_novita_api_url_and_warns_for_api_base(monkeypatch, mock_novita_client):
    mock_openai, _ = mock_novita_client
    monkeypatch.setenv("NOVITA_API_URL", "https://api.url.example/openai")
    monkeypatch.setenv("NOVITA_API_BASE", "https://api.base.example/openai")

    with pytest.warns(DeprecationWarning, match="NOVITA_API_BASE"):
        NovitaLLM(NovitaConfig(api_key="api_key"))

    assert mock_openai.call_args.kwargs["base_url"] == "https://api.url.example/openai"


def test_generate_response_passes_response_format(mock_novita_client):
    _, mock_client = mock_novita_client
    config = NovitaConfig(model="deepseek/deepseek-v3.2", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = NovitaLLM(config)
    messages = [{"role": "user", "content": "Return JSON"}]
    response_format = {"type": "json_object"}

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content='{"ok": true}'))]
    mock_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages, response_format=response_format)

    assert mock_client.chat.completions.create.call_args.kwargs["response_format"] == response_format


def test_novita_response_callback_invoked(mock_novita_client):
    _, mock_client = mock_novita_client
    callback = Mock()
    llm = NovitaLLM(NovitaConfig(model="deepseek/deepseek-v3.2", response_callback=callback))
    messages = [{"role": "user", "content": "Test callback"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="ok"))]
    mock_client.chat.completions.create.return_value = mock_response

    llm.generate_response(messages)

    callback.assert_called_once()
    args = callback.call_args[0]
    assert args[0] is llm
    assert args[1] == mock_response
    assert "messages" in args[2]
