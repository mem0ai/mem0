import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.cohere import CohereLlm


@pytest.fixture
def cohere_llm_config():
    os.environ["COHERE_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(model="command-r", max_tokens=100, temperature=0.7, top_p=0.8, token_usage=False)
    yield config
    os.environ.pop("COHERE_API_KEY")


def test_init_raises_value_error_without_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    with pytest.raises(ValueError):
        CohereLlm()


def test_get_llm_model_answer_raises_value_error_for_system_prompt(cohere_llm_config):
    llm = CohereLlm(cohere_llm_config)
    llm.config.system_prompt = "system_prompt"
    with pytest.raises(ValueError):
        llm.get_llm_model_answer("prompt")


def test_get_llm_model_answer(cohere_llm_config, mocker):
    mocker.patch("embedchain.llm.cohere.CohereLlm._get_answer", return_value="Test answer")

    llm = CohereLlm(cohere_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"


def test_get_llm_model_answer_with_token_usage(cohere_llm_config, mocker):
    test_config = BaseLlmConfig(
        temperature=cohere_llm_config.temperature,
        max_tokens=cohere_llm_config.max_tokens,
        top_p=cohere_llm_config.top_p,
        model=cohere_llm_config.model,
        token_usage=True,
    )
    mocker.patch(
        "embedchain.llm.cohere.CohereLlm._get_answer",
        return_value=("Test answer", {"input_tokens": 1, "output_tokens": 2}),
    )

    llm = CohereLlm(test_config)
    answer, token_info = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    assert token_info == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "total_cost": 3.5e-06,
        "cost_currency": "USD",
    }


def test_get_answer_mocked_cohere(cohere_llm_config, mocker):
    mocked_cohere = mocker.patch("embedchain.llm.cohere.ChatCohere")
    mocked_cohere.return_value.invoke.return_value.content = "Mocked answer"

    llm = CohereLlm(cohere_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"
