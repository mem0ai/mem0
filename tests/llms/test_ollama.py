from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.ollama import OllamaConfig
from mem0.llms.ollama import OllamaLLM


@pytest.fixture
def mock_ollama_client():
    with patch("mem0.llms.ollama.Client") as mock_ollama:
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "llama3.1:70b"}]}
        mock_ollama.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_ollama_client):
    config = OllamaConfig(model="llama3.1:70b", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OllamaLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = {"message": {"content": "I'm doing well, thank you for asking!"}}
    mock_ollama_client.chat.return_value = mock_response

    response = llm.generate_response(messages)

    mock_ollama_client.chat.assert_called_once_with(
        model="llama3.1:70b", messages=messages, options={"temperature": 0.7, "num_predict": 100, "top_p": 1.0}
    )
    assert response == "I'm doing well, thank you for asking!"
