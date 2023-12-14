import pytest

from embedchain.config import BaseLlmConfig
from embedchain.llm.google import GoogleLlm


@pytest.fixture
def google_llm_config():
    return BaseLlmConfig(model="gemini-pro", max_tokens=100, temperature=0.7, top_p=0.5, stream=False)


def test_google_llm_init_missing_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="Please set the GOOGLE_API_KEY environment variable."):
        GoogleLlm()


def test_google_llm_init(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_api_key")
    with monkeypatch.context() as m:
        m.setattr("importlib.import_module", lambda x: None)
        google_llm = GoogleLlm()
    assert google_llm is not None


def test_google_llm_get_llm_model_answer_with_system_prompt(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "fake_api_key")
    monkeypatch.setattr("importlib.import_module", lambda x: None)
    google_llm = GoogleLlm(config=BaseLlmConfig(system_prompt="system prompt"))
    with pytest.raises(ValueError, match="GoogleLlm does not support `system_prompt`"):
        google_llm.get_llm_model_answer("test prompt")


def test_google_llm_get_llm_model_answer(monkeypatch, google_llm_config):
    def mock_get_answer(prompt, config):
        return "Generated Text"

    monkeypatch.setenv("GOOGLE_API_KEY", "fake_api_key")
    monkeypatch.setattr(GoogleLlm, "_get_answer", mock_get_answer)
    google_llm = GoogleLlm(config=google_llm_config)
    result = google_llm.get_llm_model_answer("test prompt")

    assert result == "Generated Text"
