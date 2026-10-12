from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.openai import OpenAIConfig
from mem0.llms.openai_structured import OpenAIStructuredLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai_structured.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def _mock_parse(mock_client, content="ok"):
    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content=content))]
    mock_client.beta.chat.completions.parse.return_value = mock_response


def test_reasoning_model_drops_temperature(mock_openai_client):
    """Reasoning models reject `temperature`; structured output must not send it."""
    config = OpenAIConfig(model="o3-mini", reasoning_effort="low")
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert "temperature" not in call_kwargs  # reasoning models don't accept temperature
    assert "max_tokens" not in call_kwargs  # also dropped for reasoning models
    assert "top_p" not in call_kwargs  # also dropped for reasoning models
    assert call_kwargs["reasoning_effort"] == "low"
    assert call_kwargs["model"] == "o3-mini"


def test_regular_model_sends_sampling_params(mock_openai_client):
    """Regular models still receive the standard sampling params."""
    config = OpenAIConfig(model="gpt-4o", temperature=0.3)
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert call_kwargs["temperature"] == 0.3
    assert "max_tokens" in call_kwargs  # standard sampling params still forwarded
    assert "top_p" in call_kwargs
    assert call_kwargs["model"] == "gpt-4o"


def test_uses_openai_base_url_environment_variable(monkeypatch):
    base_url = "https://gateway.example/v1"
    monkeypatch.setenv("OPENAI_API_BASE", "https://legacy.example/v1")
    monkeypatch.setenv("OPENAI_BASE_URL", base_url)

    with patch("mem0.llms.openai_structured.OpenAI") as mock_openai:
        OpenAIStructuredLLM(OpenAIConfig(api_key="test-api-key"))

    mock_openai.assert_called_once_with(api_key="test-api-key", base_url=base_url)


def test_store_not_sent_by_default(mock_openai_client):
    """`store` must NOT be injected into structured-output requests when the
    user has not explicitly configured it (opt-in, mirroring OpenAILLM)."""
    config = OpenAIConfig(model="gpt-5-mini")
    assert config.store is None  # opt-in default
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args.kwargs
    assert "store" not in call_kwargs


def test_store_sent_when_explicitly_true(mock_openai_client):
    """When the user explicitly sets `store=True`, the field must be forwarded
    to structured-output requests as well (issue #7595)."""
    config = OpenAIConfig(model="gpt-5-mini", store=True)
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args.kwargs
    assert call_kwargs["store"] is True


def test_store_sent_when_explicitly_false(mock_openai_client):
    """An explicit `store=False` opt-out must still be forwarded."""
    config = OpenAIConfig(model="gpt-5-mini", store=False)
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client)

    llm.generate_response([{"role": "user", "content": "Hello"}])

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args.kwargs
    assert call_kwargs["store"] is False


def test_response_callback_invocation(mock_openai_client):
    """`response_callback` must fire for structured completions, mirroring
    OpenAILLM, with (llm_instance, raw_response, params)."""
    mock_callback = Mock()

    config = OpenAIConfig(model="gpt-5-mini", response_callback=mock_callback)
    llm = OpenAIStructuredLLM(config)
    messages = [{"role": "user", "content": "Test callback"}]
    _mock_parse(mock_openai_client)

    llm.generate_response(messages)

    mock_callback.assert_called_once()
    args = mock_callback.call_args[0]
    assert args[0] is llm  # llm_instance
    assert args[1] is mock_openai_client.beta.chat.completions.parse.return_value  # raw_response
    assert "messages" in args[2]  # params


def test_callback_exception_handling(mock_openai_client):
    """A faulty callback must not break structured response generation."""

    def faulty_callback(*args):
        raise ValueError("Callback error")

    config = OpenAIConfig(model="gpt-5-mini", response_callback=faulty_callback)
    llm = OpenAIStructuredLLM(config)
    _mock_parse(mock_openai_client, content="Expected response")

    response = llm.generate_response([{"role": "user", "content": "Test exception"}])

    assert response == "Expected response"
    assert llm.config.response_callback is faulty_callback
