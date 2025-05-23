import os
from unittest.mock import patch, MagicMock

import pytest
from langchain.schema import HumanMessage, SystemMessage
from langchain_anthropic import ChatAnthropic

from embedchain.config import BaseLlmConfig
from embedchain.llm.anthropic import AnthropicLlm


@pytest.fixture
def anthropic_llm():
    os.environ["ANTHROPIC_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(temperature=0.5, model="claude-instant-1", token_usage=False)
    return AnthropicLlm(config)


def test_get_llm_model_answer(anthropic_llm):
    with patch.object(AnthropicLlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = anthropic_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt, anthropic_llm.config)


def test_get_messages(anthropic_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = anthropic_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]


def test_get_llm_model_answer_with_token_usage(anthropic_llm):
    test_config = BaseLlmConfig(
        temperature=anthropic_llm.config.temperature, model=anthropic_llm.config.model, token_usage=True
    )
    anthropic_llm.config = test_config
    with patch.object(
        AnthropicLlm, "_get_answer", return_value=("Test Response", {"input_tokens": 1, "output_tokens": 2})
    ) as mock_method:
        prompt = "Test Prompt"
        response, token_info = anthropic_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        assert token_info == {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "total_cost": 1.265e-05,
            "cost_currency": "USD",
        }
        mock_method.assert_called_once_with(prompt, anthropic_llm.config)


def test_anthropic_llm_config_options_passed_to_chat_anthropic(anthropic_llm):
    test_api_key = "override_api_key"
    test_model_kwargs = {"param1": "value1", "param2": "value2"}
    test_callbacks = [MagicMock()]
    test_default_headers = {"X-Test-Header": "TestValue"}
    test_http_client = MagicMock()

    config = BaseLlmConfig(
        temperature=0.7,
        model="claude-2",
        api_key=test_api_key,
        max_tokens=500,
        top_p=0.9,
        base_url="https://api.example.com",
        model_kwargs=test_model_kwargs,
        token_usage=False,  # Set to False to simplify mocking _get_answer's direct return
        callbacks=test_callbacks,
        default_headers=test_default_headers,
        http_client=test_http_client,
    )
    anthropic_llm_instance = AnthropicLlm(config)

    # Mock the ChatAnthropic class itself to inspect its instantiation arguments
    with patch("embedchain.llm.anthropic.ChatAnthropic", autospec=True) as mock_chat_anthropic_class:
        # Create a mock instance for the class to return, so we can mock its methods
        mock_chat_instance = MagicMock()
        mock_chat_instance.invoke.return_value = MagicMock(content="Mocked AI Response")
        mock_chat_anthropic_class.return_value = mock_chat_instance

        anthropic_llm_instance.get_llm_model_answer("Test Prompt")

        mock_chat_anthropic_class.assert_called_once()
        called_args, called_kwargs = mock_chat_anthropic_class.call_args

        assert called_kwargs.get("anthropic_api_key") == test_api_key
        assert called_kwargs.get("temperature") == 0.7
        assert called_kwargs.get("model_name") == "claude-2"
        assert called_kwargs.get("max_tokens") == 500
        assert called_kwargs.get("top_p") == 0.9
        assert called_kwargs.get("anthropic_api_url") == "https://api.example.com"
        assert called_kwargs.get("callbacks") == test_callbacks
        assert called_kwargs.get("default_headers") == test_default_headers
        assert called_kwargs.get("client") == test_http_client
        # Check that model_kwargs were correctly passed and unpacked
        assert called_kwargs.get("param1") == "value1"
        assert called_kwargs.get("param2") == "value2"

        # Ensure invoke was called on the instance
        mock_chat_instance.invoke.assert_called_once()
