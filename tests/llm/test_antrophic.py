import pytest
from unittest.mock import MagicMock, patch

from embedchain.llm.antrophic import AntrophicLlm
from embedchain.config import BaseLlmConfig
from langchain.schema import HumanMessage, SystemMessage


@pytest.fixture
def antrophic_llm():
    config = BaseLlmConfig(temperature=0.5, model="gpt2")
    return AntrophicLlm(config)


def test_get_llm_model_answer(antrophic_llm):
    with patch.object(AntrophicLlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = antrophic_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt=prompt, config=antrophic_llm.config)


def test_get_answer(antrophic_llm):
    with patch("langchain.chat_models.ChatAnthropic") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        response = antrophic_llm._get_answer(prompt, antrophic_llm.config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(
            temperature=antrophic_llm.config.temperature, model=antrophic_llm.config.model
        )
        mock_chat_instance.assert_called_once_with(
            antrophic_llm._get_messages(prompt, system_prompt=antrophic_llm.config.system_prompt)
        )


def test_get_messages(antrophic_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = antrophic_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]


def test_get_answer_max_tokens_is_provided(antrophic_llm, caplog):
    with patch("langchain.chat_models.ChatAnthropic") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        config = antrophic_llm.config
        config.max_tokens = 500

        response = antrophic_llm._get_answer(prompt, config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(temperature=config.temperature, model=config.model)

        assert "Config option `max_tokens` is not supported by this model." in caplog.text
