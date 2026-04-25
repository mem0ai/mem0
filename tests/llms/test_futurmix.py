from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.futurmix import FuturMixLLM


@pytest.fixture
def mock_futurmix_client():
    with patch("mem0.llms.futurmix.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_futurmix_client):
    config = BaseLlmConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = FuturMixLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
    mock_futurmix_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_futurmix_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"
