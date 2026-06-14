from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.openai_structured import OpenAIStructuredLLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai_structured.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_reasoning_model_strips_temperature(mock_openai_client):
    """Reasoning models (o3) should not receive temperature param."""
    config = BaseLlmConfig(model="o3", api_key="test")
    llm = OpenAIStructuredLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert "temperature" not in call_kwargs
    assert call_kwargs["model"] == "o3"
    assert call_kwargs["messages"] == messages


def test_regular_model_includes_temperature(mock_openai_client):
    """Regular models should receive temperature param."""
    config = BaseLlmConfig(model="gpt-4o-2024-08-06", temperature=0.5, api_key="test")
    llm = OpenAIStructuredLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Response"))]
    mock_openai_client.beta.chat.completions.parse.return_value = mock_response

    llm.generate_response(messages)

    call_kwargs = mock_openai_client.beta.chat.completions.parse.call_args[1]
    assert call_kwargs["temperature"] == 0.5
    assert call_kwargs["model"] == "gpt-4o-2024-08-06"
