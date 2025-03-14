from unittest.mock import Mock, patch
import os
import pytest

from mem0.configs.llms.base import BaseLlmConfig
from mem0.llms.openai import OpenAILLM


@pytest.fixture
def mock_openai_client():
    with patch("mem0.llms.openai.OpenAI") as mock_openai:
        mock_client = Mock()
        mock_openai.return_value = mock_client
        yield mock_client


def test_openai_llm_base_url():
    # case1: default config: with openai official base url
    config = BaseLlmConfig(
        model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == "https://api.openai.com/v1/"

    # case2: with env variable OPENAI_API_BASE
    provider_base_url = "https://api.provider.com/v1"
    os.environ["OPENAI_API_BASE"] = provider_base_url
    config = BaseLlmConfig(
        model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0, api_key="api_key"
    )
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == provider_base_url + "/"

    # case3: with config.openai_base_url
    config_base_url = "https://api.config.com/v1"
    config = BaseLlmConfig(
        model="gpt-4o",
        temperature=0.7,
        max_tokens=100,
        top_p=1.0,
        api_key="api_key",
        openai_base_url=config_base_url,
    )
    llm = OpenAILLM(config)
    # Note: openai client will parse the raw base_url into a URL object, which will have a trailing slash
    assert str(llm.client.base_url) == config_base_url + "/"


def test_generate_response(mock_openai_client):
    config = BaseLlmConfig(model="gpt-4o", temperature=0.7, max_tokens=100, top_p=1.0)
    llm = OpenAILLM(config)
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello, how are you?"},
    ]

    mock_response = Mock()
    mock_response.choices = [
        Mock(message=Mock(content="I'm doing well, thank you for asking!"))
    ]
    mock_openai_client.chat.completions.create.return_value = mock_response

    response = llm.generate_response(messages)

    mock_openai_client.chat.completions.create.assert_called_once_with(
        model="gpt-4o", messages=messages, temperature=0.7, max_tokens=100, top_p=1.0
    )
    assert response == "I'm doing well, thank you for asking!"
