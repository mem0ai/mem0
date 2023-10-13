from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.llm.vertex_ai import VertexAILlm


@pytest.fixture
def vertexai_llm():
    config = BaseLlmConfig(temperature=0.6, model="vertexai_model", system_prompt="System Prompt")
    return VertexAILlm(config)


def test_get_llm_model_answer(vertexai_llm):
    with patch.object(VertexAILlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = vertexai_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt=prompt, config=vertexai_llm.config)


def test_get_answer_with_warning(vertexai_llm, caplog):
    with patch("langchain.chat_models.ChatVertexAI") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        config = vertexai_llm.config
        config.top_p = 0.5

        response = vertexai_llm._get_answer(prompt, config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(temperature=config.temperature, model=config.model)

        assert "Config option `top_p` is not supported by this model." in caplog.text


def test_get_answer_no_warning(vertexai_llm, caplog):
    with patch("langchain.chat_models.ChatVertexAI") as mock_chat:
        mock_chat_instance = mock_chat.return_value
        mock_chat_instance.return_value = MagicMock(content="Test Response")

        prompt = "Test Prompt"
        config = vertexai_llm.config
        config.top_p = 1.0

        response = vertexai_llm._get_answer(prompt, config)

        assert response == "Test Response"
        mock_chat.assert_called_once_with(temperature=config.temperature, model=config.model)

        assert "Config option `top_p` is not supported by this model." not in caplog.text


def test_get_messages(vertexai_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = vertexai_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]
