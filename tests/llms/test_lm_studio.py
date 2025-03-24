from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.lmstudio import LMStudioLLM


@pytest.fixture
def mock_lm_studio_client():
    with patch("mem0.llms.lmstudio.Client") as mock_lm_studio:
        mock_client = Mock()
        mock_client.list.return_value = {"models": [{"name": "lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf"}]}
        mock_lm_studio.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_lm_studio_client):
    config = BaseLlmConfig(model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = LMStudioLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = {"message": {"content": "I'm doing well, thank you for asking!"}}
    mock_lm_studio_client.chat.return_value = mock_response

    response = llm.generate_response(messages)

    mock_lm_studio_client.chat.assert_called_once_with(
        model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf", messages=messages, options={"temperature": 0.7, "num_predict": 100, "top_p": 1.0}
    )
    assert response == "I'm doing well, thank you for asking!"
