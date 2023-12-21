import pytest
from langchain.llms.ollama import Ollama as LangchainOllama

from embedchain.config import BaseLlmConfig
from embedchain.llm.ollama import OllamaLlm


@pytest.fixture
def config():
    config = BaseLlmConfig(
        temperature=0.7,
        top_p=0.8,
        stream=False,
        system_prompt="System prompt",
        model="llama2",
    )
    yield config


@pytest.fixture
def ollama_with_config(config):
    return OllamaLlm(config=config)


@pytest.fixture
def ollama_without_config():
    return OllamaLlm()


def test_ollama_init_with_config(config, ollama_with_config):
    assert ollama_with_config.config.temperature == config.temperature
    assert ollama_with_config.config.top_p == config.top_p
    assert ollama_with_config.config.stream == config.stream
    assert ollama_with_config.config.system_prompt == config.system_prompt
    assert ollama_with_config.config.model == config.model

    assert isinstance(ollama_with_config.instance, LangchainOllama)


def test_ollama_init_without_config(ollama_without_config):
    assert ollama_without_config.config.model == "llama2"
    assert isinstance(ollama_without_config.instance, LangchainOllama)


def test_get_llm_model_answer(mocker, ollama_with_config):
    test_query = "Test query"
    test_answer = "Test answer"

    mocked_get_answer = mocker.patch("embedchain.llm.ollama.OllamaLlm._get_answer", return_value=test_answer)
    answer = ollama_with_config.get_llm_model_answer(test_query)

    assert answer == test_answer
    mocked_get_answer.assert_called_once_with(prompt=test_query, config=ollama_with_config.config)
