import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.together import TogetherLlm


@pytest.fixture
def together_llm_config():
    os.environ["TOGETHER_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(model="together-ai-up-to-3b", max_tokens=50, temperature=0.7, top_p=0.8)
    yield config
    os.environ.pop("TOGETHER_API_KEY")


def test_init_raises_value_error_without_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    with pytest.raises(ValueError):
        TogetherLlm()


def test_get_llm_model_answer_raises_value_error_for_system_prompt(together_llm_config):
    llm = TogetherLlm(together_llm_config)
    llm.config.system_prompt = "system_prompt"
    with pytest.raises(ValueError):
        llm.get_llm_model_answer("prompt")


def test_get_llm_model_answer(together_llm_config, mocker):
    mocker.patch("embedchain.llm.together.TogetherLlm._get_answer", return_value="Test answer")

    llm = TogetherLlm(together_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"


def test_get_llm_model_answer_with_token_usage(together_llm_config, mocker):
    test_config = BaseLlmConfig(
        temperature=together_llm_config.temperature,
        max_tokens=together_llm_config.max_tokens,
        top_p=together_llm_config.top_p,
        model=together_llm_config.model,
        token_usage=True,
    )
    mocker.patch(
        "embedchain.llm.together.TogetherLlm._get_answer",
        return_value=("Test answer", {"prompt_tokens": 1, "completion_tokens": 2}),
    )

    llm = TogetherLlm(test_config)
    answer, token_info = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    assert token_info == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "total_cost": 3e-07,
        "cost_currency": "USD",
    }


def test_get_answer_mocked_together(together_llm_config, mocker):
    mocked_together = mocker.patch("embedchain.llm.together.ChatTogether")
    mock_instance = mocked_together.return_value
    mock_instance.invoke.return_value.content = "Mocked answer"

    llm = TogetherLlm(together_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"
