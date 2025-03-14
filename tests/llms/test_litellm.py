from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms import litellm


@pytest.fixture
def mock_litellm():
    with patch("mem0.llms.litellm.litellm") as mock_litellm:
        yield mock_litellm


def test_generate_response_with_unsupported_model(mock_litellm):
    config = BaseLlmConfig(
        model="unsupported-model", temperature=0.7, max_tokens=100, top_p=1
    )
    llm = litellm.LiteLLM(config)
    messages = [{"role": "user", "content": "Hello"}]

    mock_litellm.supports_function_calling.return_value = False

    with pytest.raises(
        ValueError,
        match="Model 'unsupported-model' in LiteLLM does not support function calling.",
    ):
        llm.generate_response(messages)


def test_generate_response(mock_litellm):
    config = BaseLlmConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1)
    llm = litellm.LiteLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="I'm doing well, thank you for asking!"))
    ]
    mock_litellm.completion.return_value = mock_response
    mock_litellm.supports_function_calling.return_value = True

    response = llm.generate_response(messages)

    mock_litellm.completion.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"
