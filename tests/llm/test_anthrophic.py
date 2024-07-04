import os
from unittest.mock import patch

import pytest
from langchain.schema import HumanMessage, SystemMessage

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
