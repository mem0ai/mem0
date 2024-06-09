from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import HumanMessage, SystemMessage
from langchain_google_vertexai import ChatVertexAI

from embedchain.config import BaseLlmConfig
from embedchain.llm.vertex_ai import VertexAILlm


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
        token_usage=True
    )
    vertexai_llm.config = test_config
    with patch.object(VertexAILlm, "_get_answer", return_value=("Test Response", {"prompt_token_count": 1, "candidates_token_count": 2})):
        response, token_info = vertexai_llm.get_llm_model_answer("Test Query")
        assert response == "Test Response"
        assert token_info == {"input_tokens": 1, "output_tokens": 2, "total_cost (USD)": 3.75e-07}


@pytest.mark.skip(
    reason="Requires mocking of Google Console Auth. Revisit later since don't want to block users right now."
)
def test_get_answer(vertexai_llm, caplog):
    with patch.object(ChatVertexAI, "invoke", return_value=MagicMock(content="Test Response")) as mock_method:
        config = vertexai_llm.config
        prompt = "Test Prompt"
        messages = vertexai_llm._get_messages(prompt)
        response = vertexai_llm._get_answer(prompt, config)
        mock_method.assert_called_once_with(messages)

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
