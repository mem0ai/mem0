import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.mistralai import MistralAILlm


@pytest.fixture
def mistralai_llm_config(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake_api_key")
    yield BaseLlmConfig(model="mistral-tiny", max_tokens=100, temperature=0.7, top_p=0.5, stream=False)
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)


def test_mistralai_llm_init_missing_api_key(monkeypatch):
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Please set the MISTRAL_API_KEY environment variable."):
        MistralAILlm()


def test_mistralai_llm_init(monkeypatch):
    monkeypatch.setenv("MISTRAL_API_KEY", "fake_api_key")
    llm = MistralAILlm()
    assert llm is not None


def test_get_llm_model_answer(monkeypatch, mistralai_llm_config):
    def mock_get_answer(self, prompt, config):
        return "Generated Text"

    monkeypatch.setattr(MistralAILlm, "_get_answer", mock_get_answer)
    llm = MistralAILlm(config=mistralai_llm_config)
    result = llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"


def test_get_llm_model_answer_with_system_prompt(monkeypatch, mistralai_llm_config):
    mistralai_llm_config.system_prompt = "Test system prompt"
    monkeypatch.setattr(MistralAILlm, "_get_answer", lambda self, prompt, config: "Generated Text")
    llm = MistralAILlm(config=mistralai_llm_config)
    result = llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"


def test_get_llm_model_answer_empty_prompt(monkeypatch, mistralai_llm_config):
    monkeypatch.setattr(MistralAILlm, "_get_answer", lambda self, prompt, config: "Generated Text")
    llm = MistralAILlm(config=mistralai_llm_config)
    result = llm.get_llm_model_answer("")

    assert result == "Generated Text"


def test_get_llm_model_answer_without_system_prompt(monkeypatch, mistralai_llm_config):
    mistralai_llm_config.system_prompt = None
    monkeypatch.setattr(MistralAILlm, "_get_answer", lambda self, prompt, config: "Generated Text")
    llm = MistralAILlm(config=mistralai_llm_config)
    result = llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"


def test_get_llm_model_answer_with_token_usage(monkeypatch, mistralai_llm_config):
    test_config = BaseLlmConfig(
        temperature=mistralai_llm_config.temperature,
        max_tokens=mistralai_llm_config.max_tokens,
        top_p=mistralai_llm_config.top_p,
        model=mistralai_llm_config.model,
        token_usage=True,
    )
    monkeypatch.setattr(
        MistralAILlm,
        "_get_answer",
        lambda self, prompt, config: ("Generated Text", {"prompt_tokens": 1, "completion_tokens": 2}),
    )

    llm = MistralAILlm(test_config)
    answer, token_info = llm.get_llm_model_answer("Test query")

    assert answer == "Generated Text"
    assert token_info == {
        "prompt_tokens": 1,
        "completion_tokens": 2,
        "total_tokens": 3,
        "total_cost": 7.5e-07,
        "cost_currency": "USD",
    }
