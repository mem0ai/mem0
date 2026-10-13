import pytest

from mem0.llms.configs import LlmConfig
from mem0.utils.factory import LlmFactory


def test_builtin_provider_is_accepted():
    # Built-in providers must continue to validate after the fix.
    assert LlmConfig(provider="openai", config={}).provider == "openai"
    assert LlmConfig(provider="anthropic", config={}).provider == "anthropic"


def test_unknown_provider_is_rejected():
    with pytest.raises(ValueError):
        LlmConfig(provider="this_provider_does_not_exist_xyz", config={})


def test_registered_provider_passes_validation():
    # Reproduces mem0ai/mem0#7625: a provider registered via the public
    # LlmFactory.register_provider API must be accepted by LlmConfig, instead of
    # raising "Unsupported LLM provider".
    LlmFactory.register_provider("verified", "mypkg.VerifiedLLM")
    try:
        cfg = LlmConfig(provider="verified", config={})
        assert cfg.provider == "verified"
    finally:
        LlmFactory.provider_to_class.pop("verified", None)
        cfg_mod = __import__("mem0.llms.configs", fromlist=["SUPPORTED_LLM_PROVIDERS"])
        sp = getattr(cfg_mod, "SUPPORTED_LLM_PROVIDERS", None)
        if sp is not None:
            sp.discard("verified")
