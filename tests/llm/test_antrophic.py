from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.llm.anthropic import AnthropicLlm


@pytest.fixture
def anthropic_llm():
    config = BaseLlmConfig(temperature=0.5, model="gpt2")
    return AnthropicLlm(config)


def test_get_llm_model_answer(anthropic_llm):
    with patch.object(AnthropicLlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = anthropic_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt=prompt, config=anthropic_llm.config)


def test_get_answer(anthropic_llm):
    with patch("langchain.chat_models.ChatAnthropic") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        response = anthropic_llm._get_answer(prompt, anthropic_llm.config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(
            temperature=anthropic_llm.config.temperature, model=anthropic_llm.config.model
        )
        mock_chat_instance.assert_called_once_with(
            anthropic_llm._get_messages(prompt, system_prompt=anthropic_llm.config.system_prompt)
        )


def test_get_messages(anthropic_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = anthropic_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]


def test_get_answer_max_tokens_is_provided(anthropic_llm, caplog):
    with patch("langchain.chat_models.ChatAnthropic") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        config = anthropic_llm.config
        config.max_tokens = 500

        response = anthropic_llm._get_answer(prompt, config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(temperature=config.temperature, model=config.model)

        assert "Config option `max_tokens` is not supported by this model." in caplog.text
