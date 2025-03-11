from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.groq import GroqLLM


@pytest.fixture
def mock_groq_client():
    with patch("mem0.llms.groq.Groq") as mock_groq:
        mock_client = Mock()
        mock_groq.return_value = mock_client
        yield mock_client


def test_generate_response(mock_groq_client):
    config = BaseLlmConfig(
        model="llama3-70b-8192", temperature=0.7, max_tokens=100, top_p=1.0
    )
    llm = GroqLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="I'm doing well, thank you for asking!"))
    ]
    mock_groq_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_groq_client.chat.completions.create.assert_called_once_with(
        model="llama3-70b-8192",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    assert response == "I'm doing well, thank you for asking!"
