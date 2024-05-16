import pytest

from embedchain.llm.premai import PremAIConfig, PremAILlm


@pytest.fixture
def premai_llm_config(monkeypatch):
    monkeypatch.setenv("PREMAI_API_KEY", "fake_api_key")
    yield PremAIConfig(project_id=1111, max_tokens=100, temperature=0.7, top_p=0.5, stream=False)
    monkeypatch.delenv("PREMAI_API_KEY", raising=False)


def test_premai_llm_init_missing_api_key(monkeypatch):
    monkeypatch.delenv("PREMAI_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Please set PREMAI_API_KEY environment variable or pass in the config."):
        PremAILlm(config=PremAIConfig(project_id=1111))


def test_premai_llm_init(monkeypatch):
    monkeypatch.setenv("PREMAI_API_KEY", "fake_api_key")
    llm = PremAILlm(config=PremAIConfig(project_id=1111))
    assert llm is not None


def test_get_llm_model_answer(monkeypatch, premai_llm_config):
    def mock_get_answer(client, prompt, config):
        return "Generated Text"

    monkeypatch.setattr(PremAILlm, "_get_answer", mock_get_answer)
    llm = PremAILlm(config=premai_llm_config)
    result = llm.get_llm_model_answer("test prompt")
    assert result == "Generated Text"


def test_get_llm_model_answer_with_system_prompt(monkeypatch, premai_llm_config):
    premai_llm_config.system_prompt = "Test system prompt"
    monkeypatch.setattr(PremAILlm, "_get_answer", lambda client, prompt, config: "Generated Text")
    llm = PremAILlm(config=premai_llm_config)
    result = llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"


def test_get_llm_model_answer_without_system_prompt(monkeypatch, premai_llm_config):
    premai_llm_config.system_prompt = None
    monkeypatch.setattr(PremAILlm, "_get_answer", lambda client, prompt, config: "Generated Text")
    llm = PremAILlm(config=premai_llm_config)
    result = llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"


def test_get_llm_model_answer_empty_prompt(monkeypatch, premai_llm_config):
    monkeypatch.setattr(PremAILlm, "_get_answer", lambda client, prompt, config: "Generated Text")
    llm = PremAILlm(config=premai_llm_config)
    result = llm.get_llm_model_answer("")

    assert result == "Generated Text"
