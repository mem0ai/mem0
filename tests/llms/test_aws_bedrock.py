from unittest.mock import MagicMock, patch

import pytest

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig
from mem0.llms.aws_bedrock import AWSBedrockLLM, extract_provider
from mem0.utils.factory import LlmFactory


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_boto3():
    """Patch boto3 so no real AWS calls are made during unit tests."""
    with patch("mem0.llms.aws_bedrock.boto3") as mock_b3:
        runtime_client = MagicMock()
        bedrock_client = MagicMock()
        bedrock_client.list_foundation_models.return_value = {"modelSummaries": []}

        def _client(service, **kwargs):
            if service == "bedrock-runtime":
                return runtime_client
            return bedrock_client

        mock_b3.client.side_effect = _client
        yield runtime_client


def _make_llm(model: str, mock_boto3, **kwargs) -> AWSBedrockLLM:
    """Instantiate AWSBedrockLLM with a given model, all AWS calls mocked."""
    config = AWSBedrockConfig(model=model, **kwargs)
    return AWSBedrockLLM(config)


def _converse_response(text: str = "ok") -> dict:
    """Minimal Converse API response dict."""
    return {"output": {"message": {"content": [{"text": text}]}}}


# ---------------------------------------------------------------------------
# extract_provider
# ---------------------------------------------------------------------------

class TestExtractProvider:
    def test_standard_anthropic_model(self):
        assert extract_provider("anthropic.claude-3-5-sonnet-20240620-v1:0") == "anthropic"

    def test_inference_profile_us_prefix(self):
        # Cross-region inference profile IDs look like us.anthropic.<model>
        assert extract_provider("us.anthropic.claude-haiku-4-5-20251001-v1:0") == "anthropic"

    def test_inference_profile_eu_prefix(self):
        assert extract_provider("eu.anthropic.claude-sonnet-4-5-20250929-v1:0") == "anthropic"

    def test_inference_profile_ap_prefix(self):
        assert extract_provider("ap.anthropic.claude-3-opus-20240229-v1:0") == "anthropic"

    def test_amazon_model(self):
        assert extract_provider("amazon.nova-3-mini-20241119-v1:0") == "amazon"

    def test_meta_model(self):
        assert extract_provider("meta.llama3-8b-instruct-v1:0") == "meta"

    def test_mistral_model(self):
        assert extract_provider("mistral.mistral-7b-instruct-v0:2") == "mistral"

    def test_unknown_model_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            extract_provider("unknown-vendor.some-model-v1:0")


# ---------------------------------------------------------------------------
# AWSBedrockConfig
# ---------------------------------------------------------------------------

class TestAWSBedrockConfig:
    def test_top_p_defaults_to_none(self):
        config = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0")
        assert config.top_p is None

    def test_top_p_explicit_value_stored(self):
        config = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0", top_p=0.8)
        assert config.top_p == 0.8

    def test_get_model_config_excludes_top_p_by_default(self):
        config = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0", temperature=0.5)
        model_cfg = config.get_model_config()
        assert "top_p" not in model_cfg

    def test_get_model_config_includes_top_p_when_set(self):
        config = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0", top_p=0.7)
        model_cfg = config.get_model_config()
        assert model_cfg["top_p"] == 0.7

    def test_get_model_config_top_p_via_model_kwargs(self):
        """model_kwargs can supply top_p after merge; same semantics as explicit top_p."""
        config = AWSBedrockConfig(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            model_kwargs={"top_p": 0.88},
        )
        assert config.get_model_config()["top_p"] == 0.88

    def test_get_model_config_always_includes_temperature(self):
        config = AWSBedrockConfig(model="anthropic.claude-3-5-sonnet-20240620-v1:0", temperature=0.3)
        model_cfg = config.get_model_config()
        assert model_cfg["temperature"] == 0.3

    def test_aws_region_stored(self):
        config = AWSBedrockConfig(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            aws_region="us-east-2",
        )
        assert config.aws_region == "us-east-2"


# ---------------------------------------------------------------------------
# LlmFactory
# ---------------------------------------------------------------------------

class TestLlmFactory:
    def test_aws_bedrock_uses_aws_bedrock_config(self):
        _, config_class = LlmFactory.provider_to_class["aws_bedrock"]
        assert config_class is AWSBedrockConfig

    def test_factory_create_accepts_aws_region(self, mock_boto3):
        """LlmFactory.create must not crash when aws_region is in the config dict.

        Before the fix, the factory mapped aws_bedrock to BaseLlmConfig which has
        no aws_region parameter, causing: TypeError: __init__() got an unexpected
        keyword argument 'aws_region'.
        """
        user_dict = {
            "model": "anthropic.claude-3-5-sonnet-20240620-v1:0",
            "aws_region": "us-east-2",
            "temperature": 0.1,
            "max_tokens": 2000,
        }
        mock_boto3.converse.return_value = _converse_response()

        # This must not raise TypeError
        llm = LlmFactory.create("aws_bedrock", user_dict)

        assert isinstance(llm.config, AWSBedrockConfig)
        assert llm.config.aws_region == "us-east-2"
        assert llm.config.top_p is None


# ---------------------------------------------------------------------------
# _build_inference_config
# ---------------------------------------------------------------------------

class TestBuildInferenceConfig:
    """
    Unit tests for the _build_inference_config helper.
    Validates the exact keys present in the returned dict.
    """

    def test_anthropic_only_temperature_by_default(self, mock_boto3):
        llm = _make_llm("anthropic.claude-3-5-sonnet-20240620-v1:0", mock_boto3, temperature=0.5)
        cfg = llm._build_inference_config()
        assert "temperature" in cfg
        assert cfg["temperature"] == 0.5
        assert "topP" not in cfg, "topP must be absent when top_p not configured"

    def test_anthropic_top_p_explicitly_set_still_omits_top_p(self, mock_boto3):
        # Anthropic rejects both; topP must still be omitted even when set
        llm = _make_llm(
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            mock_boto3,
            temperature=0.5,
            top_p=0.9,
        )
        cfg = llm._build_inference_config()
        assert "temperature" in cfg
        assert "topP" not in cfg

    def test_anthropic_inference_profile_omits_top_p(self, mock_boto3):
        # Cross-region inference profiles (us.anthropic.*) follow the same rule
        llm = _make_llm("us.anthropic.claude-haiku-4-5-20251001-v1:0", mock_boto3, temperature=0.1)
        cfg = llm._build_inference_config()
        assert "topP" not in cfg

    def test_amazon_includes_top_p_when_set(self, mock_boto3):
        llm = _make_llm(
            "amazon.nova-3-mini-20241119-v1:0",
            mock_boto3,
            temperature=0.5,
            top_p=0.85,
        )
        cfg = llm._build_inference_config()
        assert cfg["temperature"] == 0.5
        assert cfg["topP"] == 0.85

    def test_amazon_omits_top_p_when_not_set(self, mock_boto3):
        llm = _make_llm("amazon.nova-3-mini-20241119-v1:0", mock_boto3, temperature=0.5)
        cfg = llm._build_inference_config()
        assert "topP" not in cfg

    def test_max_tokens_present(self, mock_boto3):
        llm = _make_llm(
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            mock_boto3,
            max_tokens=1024,
        )
        cfg = llm._build_inference_config()
        assert cfg["maxTokens"] == 1024

    def test_nova_fallback_max_tokens_when_absent(self, mock_boto3):
        """Legacy Nova Converse used 5000 when max_tokens was missing from the dict."""
        llm = _make_llm("amazon.nova-3-mini-20241119-v1:0", mock_boto3)
        llm.model_config.pop("max_tokens", None)
        cfg = llm._build_inference_config()
        assert cfg["maxTokens"] == 5000

    def test_anthropic_fallback_max_tokens_when_absent(self, mock_boto3):
        llm = _make_llm("anthropic.claude-3-5-sonnet-20240620-v1:0", mock_boto3)
        llm.model_config.pop("max_tokens", None)
        cfg = llm._build_inference_config()
        assert cfg["maxTokens"] == 2000

    def test_minimax_omits_top_p_when_explicitly_set(self, mock_boto3):
        # MiniMax M2.x (reasoning model) rejects both temperature and topP simultaneously.
        # Even when the user explicitly configures top_p, it must be omitted.
        llm = _make_llm(
            "minimax.minimax-m2.5",
            mock_boto3,
            temperature=0.1,
            top_p=0.9,
        )
        cfg = llm._build_inference_config()
        assert "temperature" in cfg
        assert "topP" not in cfg, "topP must be absent for MiniMax reasoning models"

    def test_minimax_only_temperature_by_default(self, mock_boto3):
        llm = _make_llm("minimax.minimax-m2.5", mock_boto3, temperature=0.1)
        cfg = llm._build_inference_config()
        assert cfg["temperature"] == 0.1
        assert "topP" not in cfg


# ---------------------------------------------------------------------------
# generate_response — Converse API call assertions
# ---------------------------------------------------------------------------

MESSAGES = [
    {"role": "system", "content": "You are a helpful assistant."},
    {"role": "user", "content": "Hello"},
]

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "add_memory",
            "description": "Store a memory",
            "parameters": {
                "type": "object",
                "properties": {"data": {"type": "string"}},
                "required": ["data"],
            },
        },
    }
]


class TestGenerateResponseConverse:
    def test_standard_anthropic_no_top_p_in_converse_call(self, mock_boto3):
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm("anthropic.claude-3-5-sonnet-20240620-v1:0", mock_boto3, temperature=0.2)

        llm.generate_response(MESSAGES)

        _, kwargs = mock_boto3.converse.call_args
        inference_cfg = kwargs["inferenceConfig"]
        assert "topP" not in inference_cfg
        assert inference_cfg["temperature"] == 0.2

    def test_standard_anthropic_inference_profile_no_top_p(self, mock_boto3):
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm("us.anthropic.claude-haiku-4-5-20251001-v1:0", mock_boto3, temperature=0.1)

        llm.generate_response(MESSAGES)

        _, kwargs = mock_boto3.converse.call_args
        assert "topP" not in kwargs["inferenceConfig"]

    def test_with_tools_anthropic_no_top_p(self, mock_boto3):
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm("anthropic.claude-3-5-sonnet-20240620-v1:0", mock_boto3, temperature=0.2)

        llm.generate_response(MESSAGES, tools=TOOLS)

        _, kwargs = mock_boto3.converse.call_args
        assert "topP" not in kwargs["inferenceConfig"]

    def test_with_tools_anthropic_top_p_set_still_omitted(self, mock_boto3):
        # Even if user explicitly sets top_p, Anthropic must not receive topP
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm(
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            mock_boto3,
            temperature=0.2,
            top_p=0.9,
        )

        llm.generate_response(MESSAGES, tools=TOOLS)

        _, kwargs = mock_boto3.converse.call_args
        assert "topP" not in kwargs["inferenceConfig"]

    def test_nova_includes_top_p_when_explicitly_set(self, mock_boto3):
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm(
            "amazon.nova-3-mini-20241119-v1:0",
            mock_boto3,
            temperature=0.5,
            top_p=0.85,
        )

        llm.generate_response(MESSAGES)

        _, kwargs = mock_boto3.converse.call_args
        assert kwargs["inferenceConfig"]["topP"] == 0.85

    def test_nova_omits_top_p_when_not_set(self, mock_boto3):
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm("amazon.nova-3-mini-20241119-v1:0", mock_boto3, temperature=0.5)

        llm.generate_response(MESSAGES)

        _, kwargs = mock_boto3.converse.call_args
        assert "topP" not in kwargs["inferenceConfig"]

    def test_anthropic_model_kwargs_top_p_still_omits_top_p_in_converse(self, mock_boto3):
        """top_p injected via model_kwargs must not add topP for Anthropic Converse."""
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm(
            "anthropic.claude-3-5-sonnet-20240620-v1:0",
            mock_boto3,
            temperature=0.2,
            model_kwargs={"top_p": 0.88},
        )

        llm.generate_response(MESSAGES)

        _, kwargs = mock_boto3.converse.call_args
        assert "topP" not in kwargs["inferenceConfig"]


# ---------------------------------------------------------------------------
# MiniMax provider
# ---------------------------------------------------------------------------

class TestMiniMaxProvider:
    """Tests for MiniMax models via Bedrock Converse API."""

    def test_extract_provider(self):
        assert extract_provider("minimax.minimax-m2.5") == "minimax"
        assert extract_provider("minimax.minimax-m2") == "minimax"

    def test_generate_response_text_only(self, mock_boto3):
        """Standard response: single text block."""
        mock_boto3.converse.return_value = _converse_response("Hello!")
        llm = _make_llm("minimax.minimax-m2.5", mock_boto3)

        result = llm.generate_response([{"role": "user", "content": "say hi"}])

        assert result == "Hello!"
        _, kwargs = mock_boto3.converse.call_args
        assert kwargs["modelId"] == "minimax.minimax-m2.5"
        assert kwargs["messages"][0]["role"] == "user"
        assert kwargs["messages"][0]["content"][0]["text"] == "say hi"

    def test_generate_response_reasoning_model(self, mock_boto3):
        """MiniMax M2.5 is a reasoning model: reasoningContent block comes before text."""
        reasoning_response = {
            "output": {
                "message": {
                    "content": [
                        {"reasoningContent": {"reasoningText": {"text": "Let me think..."}}},
                        {"text": "Hello!"},
                    ]
                }
            }
        }
        mock_boto3.converse.return_value = reasoning_response
        llm = _make_llm("minimax.minimax-m2.5", mock_boto3)

        result = llm.generate_response([{"role": "user", "content": "say hi"}])

        # Must skip reasoningContent and return the actual text block
        assert result == "Hello!"

    def test_inference_config(self, mock_boto3):
        """inferenceConfig should include maxTokens and temperature; no topP."""
        mock_boto3.converse.return_value = _converse_response()
        llm = _make_llm("minimax.minimax-m2.5", mock_boto3, temperature=0.2, max_tokens=512)

        llm.generate_response([{"role": "user", "content": "hi"}])

        _, kwargs = mock_boto3.converse.call_args
        assert kwargs["inferenceConfig"]["maxTokens"] == 512
        assert kwargs["inferenceConfig"]["temperature"] == 0.2
        assert "topP" not in kwargs["inferenceConfig"]

    def test_system_prompt_passed_correctly(self, mock_boto3):
        """System messages must be sent via top-level `system` param, not as a message role."""
        mock_boto3.converse.return_value = _converse_response('{"facts": ["test"]}')
        llm = _make_llm("minimax.minimax-m2.5", mock_boto3)

        llm.generate_response([
            {"role": "system", "content": "Return JSON only."},
            {"role": "user", "content": "Extract facts from: test"},
        ])

        _, kwargs = mock_boto3.converse.call_args
        # system prompt must be in top-level "system" key
        assert "system" in kwargs
        assert kwargs["system"][0]["text"] == "Return JSON only."
        # messages list must NOT contain a system role entry
        for msg in kwargs["messages"]:
            assert msg["role"] != "system"
        # user message must be present
        assert kwargs["messages"][0]["role"] == "user"
