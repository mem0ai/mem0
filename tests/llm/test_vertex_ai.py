from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.core.db.database import database_manager
from embedchain.llm.vertex_ai import VertexAILlm


@pytest.fixture(autouse=True)
def setup_database():
    database_manager.setup_engine()


@pytest.fixture
def vertexai_llm():
    config = BaseLlmConfig(temperature=0.6, model="chat-bison")
    return VertexAILlm(config)


def test_get_llm_model_answer(vertexai_llm):
    with patch.object(VertexAILlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = vertexai_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt, vertexai_llm.config)


def test_get_llm_model_answer_with_token_usage(vertexai_llm):
    test_config = BaseLlmConfig(
        temperature=vertexai_llm.config.temperature,
        max_tokens=vertexai_llm.config.max_tokens,
        top_p=vertexai_llm.config.top_p,
        model=vertexai_llm.config.model,
        token_usage=True,
    )
    vertexai_llm.config = test_config
    with patch.object(
        VertexAILlm,
        "_get_answer",
        return_value=("Test Response", {"prompt_token_count": 1, "candidates_token_count": 2}),
    ):
        response, token_info = vertexai_llm.get_llm_model_answer("Test Query")
        assert response == "Test Response"
        assert token_info == {
            "prompt_tokens": 1,
            "completion_tokens": 2,
            "total_tokens": 3,
            "total_cost": 3.75e-07,
            "cost_currency": "USD",
        }


@patch("embedchain.llm.vertex_ai.ChatVertexAI")
def test_get_answer(mock_chat_vertexai, vertexai_llm, caplog):
    mock_chat_vertexai.return_value.invoke.return_value = MagicMock(content="Test Response")

    config = vertexai_llm.config
    prompt = "Test Prompt"
    messages = vertexai_llm._get_messages(prompt)
    response = vertexai_llm._get_answer(prompt, config)
    mock_chat_vertexai.return_value.invoke.assert_called_once_with(messages)

    assert response == "Test Response"  # Assertion corrected
    assert "Config option `top_p` is not supported by this model." not in caplog.text


def test_get_messages(vertexai_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = vertexai_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]
