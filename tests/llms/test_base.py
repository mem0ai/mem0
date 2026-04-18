"""Unit tests for mem0.llms.base.LLMBase helpers."""

import pytest

from mem0.llms.base import LLMBase


class _DummyLLM(LLMBase):
    def generate_response(self, messages, tools=None, tool_choice="auto", **kwargs):
        return "dummy"


@pytest.fixture
def llm():
    return _DummyLLM()


@pytest.mark.parametrize(
    "model",
    [
        "o1",
        "o1-preview",
        "o1-mini",
        "o3",
        "o3-mini",
        "o3-pro",
        "o4-mini",
        "gpt-5",
        "gpt-5-mini",
        "gpt-5o",
        "gpt-5o-mini",
        "gpt-5o-micro",
        "GPT-5",
    ],
)
def test_is_reasoning_model_recognizes_reasoning_variants(llm, model):
    assert llm._is_reasoning_model(model) is True


@pytest.mark.parametrize(
    "model",
    [
        "gpt-4",
        "gpt-4.1-nano-2025-04-14",
        "gpt-4o",
        "gpt-4o-mini",
        # Decimal-versioned GPT-5 families (e.g. gpt-5.4-mini) are NOT
        # reasoning models and must retain full parameter support (issue #4738).
        "gpt-5.4-mini",
        "gpt-5.5",
        "gpt-5.0-preview",
        # Substrings that used to false-positive with the old "in" check.
        "llama-o1-chat",
        "mistral-o3-8b",
        "custom-gpt-5-adapter",
    ],
)
def test_is_reasoning_model_rejects_non_reasoning_variants(llm, model):
    assert llm._is_reasoning_model(model) is False


def test_get_supported_params_keeps_temperature_for_gpt_5_decimal(llm):
    """Regression guard for issue #4738: temperature must not be stripped
    for decimal-versioned GPT-5 models like gpt-5.4-mini."""
    llm.config.model = "gpt-5.4-mini"
    llm.config.temperature = 0.1
    llm.config.max_tokens = 2000
    llm.config.top_p = 0.1

    params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])

    assert params["temperature"] == 0.1
    assert params["max_tokens"] == 2000
    assert params["top_p"] == 0.1


def test_get_supported_params_strips_temperature_for_real_reasoning_model(llm):
    """Reasoning models (e.g. o3-mini) must keep the strict parameter whitelist."""
    llm.config.model = "o3-mini"

    params = llm._get_supported_params(messages=[{"role": "user", "content": "hi"}])

    assert "temperature" not in params
    assert "max_tokens" not in params
    assert "top_p" not in params
    assert params["messages"] == [{"role": "user", "content": "hi"}]
