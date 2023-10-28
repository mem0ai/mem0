import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.cohere import CohereLlm


@pytest.fixture
def cohere_llm_config():
    os.environ["COHERE_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(model="gptd-instruct-tft", max_tokens=50, temperature=0.7, top_p=0.8)
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


def test_get_answer_mocked_cohere(cohere_llm_config, mocker):
    mocked_cohere = mocker.patch("embedchain.llm.cohere.Cohere")
    mock_instance = mocked_cohere.return_value
    mock_instance.return_value = "Mocked answer"

    llm = CohereLlm(cohere_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"
    mocked_cohere.assert_called_once_with(
        cohere_api_key="test_api_key",
        model="gptd-instruct-tft",
        max_tokens=50,
        temperature=0.7,
        p=0.8,
    )
    mock_instance.assert_called_once_with(prompt)
