from unittest.mock import Mock, patch

from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.utils.factory import LlmFactory


def _capture_config(provider_name, config):
    """Build an LLM via the factory and return the config it was constructed with."""
    captured = {}

    def fake_llm_class(built_config):
        captured["config"] = built_config
        return Mock()

    with patch("mem0.utils.factory.load_class", return_value=fake_llm_class):
        LlmFactory.create(provider_name, config)

    return captured["config"]


def test_base_to_openai_preserves_reasoning_fields():
    base_config = BaseLlmConfig(model="o3", reasoning_effort="high", is_reasoning_model=True)

    built = _capture_config("openai", base_config)

    assert isinstance(built, OpenAIConfig)
    assert built.reasoning_effort == "high"
    assert built.is_reasoning_model is True


def test_base_to_kwargs_provider_preserves_reasoning_fields():
    # AWSBedrockConfig accepts the reasoning fields via **kwargs, so they must survive.
    base_config = BaseLlmConfig(model="amazon.nova", reasoning_effort="medium", is_reasoning_model=True)

    built = _capture_config("aws_bedrock", base_config)

    assert isinstance(built, AWSBedrockConfig)
    assert built.reasoning_effort == "medium"
    assert built.is_reasoning_model is True


def test_base_to_provider_without_reasoning_fields_still_builds():
    # Anthropic config does not accept reasoning_effort/is_reasoning_model;
    # the conversion must not forward unsupported kwargs to it.
    base_config = BaseLlmConfig(model="claude-3-5-sonnet-20240620")

    built = _capture_config("anthropic", base_config)

    assert isinstance(built, AnthropicConfig)
    assert built.model == "claude-3-5-sonnet-20240620"


def test_dict_config_not_mutated_by_kwargs():
    config = {"model": "gpt-4o-mini"}

    with patch("mem0.utils.factory.load_class", return_value=Mock(return_value=Mock())):
        LlmFactory.create("openai", config, api_key="secret")

    assert config == {"model": "gpt-4o-mini"}


def test_registered_provider_passes_llm_config_validation():
    """Regression test for https://github.com/mem0ai/mem0/issues/7625.

    A provider registered via LlmFactory.register_provider() must pass
    LlmConfig validation; the validator must not reject it with
    "Unsupported LLM provider". The registration is removed afterwards so
    the class-level registry is not polluted for other tests.
    """
    import pytest
    from pydantic import ValidationError

    from mem0.llms.configs import LlmConfig

    LlmFactory.register_provider("test_custom_llm", "some.module.CustomLLM")
    try:
        # The registered custom provider must validate ...
        assert LlmConfig(provider="test_custom_llm", config={}).provider == "test_custom_llm"
        # ... while built-ins keep working ...
        assert LlmConfig(provider="openai", config={}).provider == "openai"
        # ... and genuinely unknown providers are still rejected.
        with pytest.raises(ValidationError, match="Unsupported LLM provider"):
            LlmConfig(provider="not_a_real_provider", config={})
    finally:
        del LlmFactory.provider_to_class["test_custom_llm"]

    assert "test_custom_llm" not in LlmFactory.get_supported_providers()
