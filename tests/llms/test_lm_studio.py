from unittest.mock import Mock, patch

import pytest

from mem0.configs.llms.lmstudio import LMStudioConfig
from mem0.llms.lmstudio import LMStudioLLM


@pytest.fixture
def mock_lm_studio_client():
    with patch("mem0.llms.lmstudio.OpenAI") as mock_openai:  # Corrected path
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="I'm doing well, thank you for asking!"))]
        )
        mock_openai.return_value = mock_client
        yield mock_client


def test_generate_response_without_tools(mock_lm_studio_client):
    config = LMStudioConfig(
        model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    llm = LMStudioLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    response = llm.generate_response(messages)

    mock_lm_studio_client.chat.completions.create.assert_called_once_with(
        model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_object"},
    )

    assert response == "I'm doing well, thank you for asking!"


def test_generate_response_specifying_response_format(mock_lm_studio_client):
    config = LMStudioConfig(
        model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        lmstudio_response_format={"type": "json_schema"},  # Specifying the response format in config
    )
    llm = LMStudioLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    response = llm.generate_response(messages)

    mock_lm_studio_client.chat.completions.create.assert_called_once_with(
        model="lmstudio-community/Meta-Llama-3.1-8B-Instruct-GGUF/Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        response_format={"type": "json_schema"},
    )

    assert response == "I'm doing well, thank you for asking!"
