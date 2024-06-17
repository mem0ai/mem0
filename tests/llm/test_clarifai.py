
import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.clarifai import ClarifaiLlm


@pytest.fixture
def clarifai_llm_config(monkeypatch):
    monkeypatch.setenv("CLARIFAI_PAT","test_api_key")
    config = BaseLlmConfig(
        model="https://clarifai.com/openai/chat-completion/models/GPT-4",
        model_kwargs={"temperature": 0.7, "max_tokens": 100},
    )
    yield config
    monkeypatch.delenv("CLARIFAI_PAT")

def test_clarifai__llm_get_llm_model_answer(clarifai_llm_config, mocker):
    mocker.patch("embedchain.llm.clarifai.ClarifaiLlm._get_answer", return_value="Test answer")
    llm = ClarifaiLlm(clarifai_llm_config)
    answer = llm.get_llm_model_answer("Test query")

    assert answer == "Test answer"
