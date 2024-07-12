import os

import pytest

from embedchain.llm.llama2 import Llama2Llm


@pytest.fixture
def llama2_llm():
    os.environ["REPLICATE_API_TOKEN"] = "test_api_token"
    llm = Llama2Llm()
    return llm


def test_init_raises_value_error_without_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    with pytest.raises(ValueError):
        Llama2Llm()


def test_get_llm_model_answer_raises_value_error_for_system_prompt(llama2_llm):
    llama2_llm.config.system_prompt = "system_prompt"
    with pytest.raises(ValueError):
        llama2_llm.get_llm_model_answer("prompt")


def test_get_llm_model_answer(llama2_llm, mocker):
    mocked_replicate = mocker.patch("embedchain.llm.llama2.Replicate")
    mocked_replicate_instance = mocker.MagicMock()
    mocked_replicate.return_value = mocked_replicate_instance
    mocked_replicate_instance.invoke.return_value = "Test answer"

    llama2_llm.config.model = "test_model"
    llama2_llm.config.max_tokens = 50
    llama2_llm.config.temperature = 0.7
    llama2_llm.config.top_p = 0.8

    answer = llama2_llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
