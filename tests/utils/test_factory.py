from unittest.mock import Mock, patch

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.configs.llms.anthropic import AnthropicConfig
from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.configs.llms.base import BaseLlmConfig
from mem0.configs.llms.openai import OpenAIConfig
from mem0.embeddings.configs import EmbedderConfig
from mem0.utils.factory import EmbedderFactory, LlmFactory


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


def _capture_embedder_config(provider_name, config):
    """Build an embedder via the factory and return the config it was constructed with."""
    captured = {}

    def fake_embedder_class(built_config):
        captured["config"] = built_config
        return Mock()

    with patch("mem0.utils.factory.load_class", return_value=fake_embedder_class):
        EmbedderFactory.create(provider_name, config, None)

    return captured["config"]


def test_embedder_factory_accepts_none_config():
    # EmbedderConfig.config is Optional[dict], so None passes validation and
    # reaches the factory (e.g. via MemoryConfig(embedder={"config": None})).
    # The factory must treat None like the default {} instead of raising.
    built = _capture_embedder_config("openai", None)

    assert isinstance(built, BaseEmbedderConfig)


def test_embedder_config_normalizes_none_to_empty_dict():
    # Sibling VectorStoreConfig normalizes a None config to {}; EmbedderConfig
    # must do the same so None never propagates past validation.
    config = EmbedderConfig(provider="openai", config=None)

    assert config.config == {}
