import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.together import TogetherLlm


@pytest.fixture
def together_llm_config():
    os.environ["TOGETHER_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(model="togethercomputer/RedPajama-INCITE-7B-Base", max_tokens=50, temperature=0.7, top_p=0.8)
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


def test_get_answer_mocked_together(together_llm_config, mocker):
    mocked_together = mocker.patch("embedchain.llm.together.Together")
    mock_instance = mocked_together.return_value
    mock_instance.return_value = "Mocked answer"

    llm = TogetherLlm(together_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"
    mocked_together.assert_called_once_with(
        together_api_key="test_api_key",
        model="togethercomputer/RedPajama-INCITE-7B-Base",
        max_tokens=50,
        temperature=0.7,
        top_p=0.8,
    )
    mock_instance.assert_called_once_with(prompt)
