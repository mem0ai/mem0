from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms import litellm


@pytest.fixture
def mock_litellm():
    with patch("mem0.llms.litellm.litellm") as mock_litellm:
        yield mock_litellm


def test_generate_response_with_unsupported_model_no_tools(mock_litellm):
    config = BaseLlmConfig(model="unsupported-model", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="hi"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = False

    response = llm.generate_response(messages)

    assert response == "hi"
    mock_litellm.supports_function_calling.assert_not_called()


def test_generate_response_without_tools(mock_litellm):
    config = BaseLlmConfig(model="gpt-4.1-nano-2025-04-14", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gpt-4.1-nano-2025-04-14", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_gpt5_uses_max_completion_tokens(mock_litellm):
    config = BaseLlmConfig(model="gpt-5.4-mini", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    llm.generate_response(messages)

    _, kwargs = mock_litellm.completion.call_args
    assert kwargs["max_completion_tokens"] == 100
    assert "max_tokens" not in kwargs


def test_generate_response_legacy_model_uses_max_tokens(mock_litellm):
    config = BaseLlmConfig(model="gpt-4.1", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="Hi"))]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    llm.generate_response(messages)

    _, kwargs = mock_litellm.completion.call_args
    assert kwargs["max_tokens"] == 100
    assert "max_completion_tokens" not in kwargs



