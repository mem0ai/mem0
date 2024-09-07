import pytest
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

from embedchain.config import BaseLlmConfig
from embedchain.llm.ollama import OllamaLlm


@pytest.fixture
def ollama_llm_config():
    config = BaseLlmConfig(model="llama2", temperature=0.7, top_p=0.8, stream=True, system_prompt=None)
    yield config


def test_get_llm_model_answer(ollama_llm_config, mocker):
    mocker.patch("embedchain.llm.ollama.Client.list", return_value={"models": [{"name": "llama2"}]})
    mocker.patch("embedchain.llm.ollama.OllamaLlm._get_answer", return_value="Test answer")

    llm = OllamaLlm(ollama_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"


def test_get_answer_mocked_ollama(ollama_llm_config, mocker):
    mocker.patch("embedchain.llm.ollama.Client.list", return_value={"models": [{"name": "llama2"}]})
    mocked_ollama = mocker.patch("embedchain.llm.ollama.Ollama")
    mock_instance = mocked_ollama.return_value
    mock_instance.invoke.return_value = "Mocked answer"

    llm = OllamaLlm(ollama_llm_config)
    prompt = "Test query"
    answer = llm.get_llm_model_answer(prompt)

    assert answer == "Mocked answer"


def test_get_llm_model_answer_with_streaming(ollama_llm_config, mocker):
    ollama_llm_config.stream = True
    ollama_llm_config.callbacks = [StreamingStdOutCallbackHandler()]
    mocker.patch("embedchain.llm.ollama.Client.list", return_value={"models": [{"name": "llama2"}]})
    mocked_ollama_chat = mocker.patch("embedchain.llm.ollama.OllamaLlm._get_answer", return_value="Test answer")

    llm = OllamaLlm(ollama_llm_config)
    llm.get_llm_model_answer("Test query")

    mocked_ollama_chat.assert_called_once()
    call_args = mocked_ollama_chat.call_args
    config_arg = call_args[1]["config"]
    callbacks = config_arg.callbacks

    assert len(callbacks) == 1
    assert isinstance(callbacks[0], StreamingStdOutCallbackHandler)
