from unittest.mock import Mock, patch
import os
import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.deepseek import DeepSeekLLM


@pytest.fixture
def mock_deepseek_client():
    with patch("mem0.llms.deepseek.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_deepseek_llm_base_url():
    # case1: default config with deepseek official base url
    config = BaseLlmConfig(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
    )
    llm = DeepSeekLLM(config)
    assert str(llm.client.base_url) == "https://api.deepseek.com"

    # case2: with env variable DEEPSEEK_API_BASE
    provider_base_url = "https://api.provider.com/v1/"
    os.environ["DEEPSEEK_API_BASE"] = provider_base_url
    config = BaseLlmConfig(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
    )
    llm = DeepSeekLLM(config)
    assert str(llm.client.base_url) == provider_base_url

    # case3: with config.deepseek_base_url
    config_base_url = "https://api.config.com/v1/"
    config = BaseLlmConfig(
        model="deepseek-chat",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        deepseek_base_url=config_base_url,
    )
    llm = DeepSeekLLM(config)
    assert str(llm.client.base_url) == config_base_url


def test_generate_response(mock_deepseek_client):
    config = BaseLlmConfig(
        model="deepseek-chat", temperature=0.7, max_tokens=100, top_p=1.0
    )
    llm = DeepSeekLLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="I'm doing well, thank you for asking!"))
    ]
    mock_deepseek_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_deepseek_client.chat.completions.create.assert_called_once_with(
        model="deepseek-chat",
        messages=messages,
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
    )
    assert response == "I'm doing well, thank you for asking!"
