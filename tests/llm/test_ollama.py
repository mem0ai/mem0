import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.ollama import OllamaLlm


@pytest.fixture
def ollama_llm_config():
    config = BaseLlmConfig(model="llama2", temperature=0.7, top_p=0.8, stream=True, system_prompt=None)
    yield config


def test_get_llm_model_answer(ollama_llm_config, mocker):
    mocker.patch("embedchain.llm.ollama.OllamaLlm._get_answer", return_value="Test answer")

    llm = OllamaLlm(ollama_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"


def test_get_answer_mocked_ollama(ollama_llm_config, mocker):
    mocked_ollama = mocker.patch("embedchain.llm.ollama.Ollama")
    mock_instance = mocked_ollama.return_value
    mock_instance.return_value = "Mocked answer"

    llm = OllamaLlm(ollama_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"
    mocked_ollama.assert_called_once_with(
        model="llama2",
        system=None,
        temperature=0.7,
        top_p=0.8,
        callback_manager=mocker.ANY,  # Use mocker.ANY to ignore the exact instance
    )
    mock_instance.assert_called_once_with(prompt)
