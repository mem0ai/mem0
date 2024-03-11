import os

import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.clarifai import ClarifaiLlm


@pytest.fixture
def clarifai_llm_config(monkeypatch):
    config = BaseLlmConfig(
        model="https://clarifai.com/openai/chat-completion/models/GPT-4",
        model_kwargs={"temperature": 0.7, "max_tokens": 100},
    )
    yield config


def test_clarifai_llm_init_missing_api_key(monkeypatch):
    monkeypatch.delenv("CLARIFAI_PAT", raising=False)
    with pytest.raises(ValueError, match="Please set the CLARIFAI_PAT environment variable."):
        ClarifaiLlm()


def test_clarifai_llm_init(monkeypatch):
    monkeypatch.setenv("CLARIFAI_PAT", "fake_api_key")
    clarifai_llm = ClarifaiLlm()
    assert clarifai_llm is not None


def test_clarifai__llm_get_llm_model_answer(monkeypatch, clarifai_llm_config):
    def mock_get_answer(prompt, config):
        return "Generated Text"

    monkeypatch.setenv("CLARIFAI_PAT", "fake_api_key")
    monkeypatch.setattr(ClarifaiLlm, "_get_answer", mock_get_answer)
    clarifai_llm = ClarifaiLlm(config=clarifai_llm_config)
    result = clarifai_llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"
