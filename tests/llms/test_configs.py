import pytest

from mem0.llms.configs import LlmConfig
from mem0.utils.factory import LlmFactory


def test_registered_provider_accepted_by_llm_config():
    LlmFactory.register_provider("verified_test_provider", "mypkg.VerifiedLLM")
    try:
        cfg = LlmConfig(provider="verified_test_provider", config={})
        assert cfg.provider == "verified_test_provider"
    finally:
        LlmFactory.provider_to_class.pop("verified_test_provider", None)


def test_unknown_provider_still_rejected():
    with pytest.raises(ValueError, match="Unsupported LLM provider"):
        LlmConfig(provider="definitely_not_a_provider_xyz", config={})


def test_builtin_providers_still_accepted():
    assert LlmConfig(provider="openai", config={}).provider == "openai"
    assert LlmConfig(provider="langchain", config={}).provider == "langchain"
