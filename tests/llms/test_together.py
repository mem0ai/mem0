from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.together import TogetherLLM


@pytest.fixture
def mock_together_client():
    with patch("mem0.llms.together.Together") as mock_together:
        mock_client = Mock()
        mock_together.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_together_client):
    config = BaseLlmConfig(model="mistralai/Mixtral-8x7B-Instruct-v0.1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_together_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_together_client.chat.completions.create.assert_called_once_with(
        model="mistralai/Mixtral-8x7B-Instruct-v0.1", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"





def test_generate_response_forwards_extra_kwargs(mock_together_client):
    """Per the LLMBase contract, extra provider-specific kwargs must be accepted and
    forwarded to the Together client (matching openai/deepseek/vllm/xai behavior)."""
    config = BaseLlmConfig(model="mistralai/Mixtral-8x7B-Instruct-v0.1", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = TogetherLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_together_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages, frequency_penalty=0.5)

    assert response == "Hi"
    call_kwargs = mock_together_client.chat.completions.create.call_args.kwargs
    assert call_kwargs["frequency_penalty"] == 0.5
