import os
from unittest.mock import patch

import pytest
from langchain.schema import HumanMessage, SystemMessage

from embedchain.config import BaseLlmConfig
from embedchain.llm.anthropic import AnthropicLlm


@pytest.fixture
def anthropic_llm():
    os.environ["ANTHROPIC_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(temperature=0.5, model="gpt2")
    return AnthropicLlm(config)


def test_get_llm_model_answer(anthropic_llm):
    with patch.object(AnthropicLlm, "_get_answer", return_value="Test Response") as mock_method:
        prompt = "Test Prompt"
        response = anthropic_llm.get_llm_model_answer(prompt)
        assert response == "Test Response"
        mock_method.assert_called_once_with(prompt=prompt, config=anthropic_llm.config)


def test_get_messages(anthropic_llm):
    prompt = "Test Prompt"
    system_prompt = "Test System Prompt"
    messages = anthropic_llm._get_messages(prompt, system_prompt)
    assert messages == [
        SystemMessage(content="Test System Prompt", additional_kwargs={}),
        HumanMessage(content="Test Prompt", additional_kwargs={}, example=False),
    ]
