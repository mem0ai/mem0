import os

import pytest
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from embedchain.config import BaseLlmConfig
from embedchain.llm.jina import JinaLlm


@pytest.fixture
def config():
    os.environ["JINACHAT_API_KEY"] = "test_api_key"
    config = BaseLlmConfig(temperature=0.7, max_tokens=50, top_p=0.8, stream=False, system_prompt="System prompt")
    yield config
    os.environ.pop("JINACHAT_API_KEY")


def test_init_raises_value_error_without_api_key(mocker):
    mocker.patch.dict(os.environ, clear=True)
    with pytest.raises(ValueError):
        JinaLlm()


def test_get_llm_model_answer(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.jina.JinaLlm._get_answer", return_value="Test answer")

    llm = JinaLlm(config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("Test query", config)


def test_get_llm_model_answer_with_system_prompt(config, mocker):
    config.system_prompt = "Custom system prompt"
    mocked_get_answer = mocker.patch("embedchain.llm.jina.JinaLlm._get_answer", return_value="Test answer")

    llm = JinaLlm(config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("Test query", config)


def test_get_llm_model_answer_empty_prompt(config, mocker):
    mocked_get_answer = mocker.patch("embedchain.llm.jina.JinaLlm._get_answer", return_value="Test answer")

    llm = JinaLlm(config)
    answer = llm.get_llm_model_answer("")

    assert answer == "Test answer"
    mocked_get_answer.assert_called_once_with("", config)


def test_get_llm_model_answer_with_streaming(config, mocker):
    config.stream = True
    mocked_jinachat = mocker.patch("embedchain.llm.jina.JinaChat")

    llm = JinaLlm(config)
    llm.get_llm_model_answer("Test query")

    mocked_jinachat.assert_called_once()
    callbacks = [callback[1]["callbacks"] for callback in mocked_jinachat.call_args_list]
    assert any(isinstance(callback[0], StreamingStdOutCallbackHandler) for callback in callbacks)


def test_get_llm_model_answer_without_system_prompt(config, mocker):
    config.system_prompt = None
    mocked_jinachat = mocker.patch("embedchain.llm.jina.JinaChat")

    llm = JinaLlm(config)
    llm.get_llm_model_answer("Test query")

    mocked_jinachat.assert_called_once_with(
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        jinachat_api_key=os.environ["JINACHAT_API_KEY"],
        model_kwargs={"top_p": config.top_p},
    )
