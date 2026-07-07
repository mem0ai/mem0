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
