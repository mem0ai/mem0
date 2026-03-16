"""Tests for AWS Bedrock LLM — temperature/topP conflict fix.

Covers:
- inferenceConfig omits topP when top_p is not set (default None)
- inferenceConfig includes topP when top_p is explicitly set
- AWSBedrockConfig defaults top_p to None
- get_model_config excludes top_p when None
- Backward compatibility: explicit top_p still works

Regression test for #3891: Claude Sonnet 4.5+ rejects requests with both
temperature and topP specified simultaneously.
"""

from unittest.mock import MagicMock, patch

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig


# ===========================================================================
# AWSBedrockConfig — top_p defaults and model config
# ===========================================================================

class TestAWSBedrockConfigTopP:
    """Test that AWSBedrockConfig handles top_p correctly."""

    def test_default_top_p_is_none(self):
        """top_p should default to None to avoid conflicts with Claude 4.5+."""
        config = AWSBedrockConfig()
        assert config.top_p is None

    def test_explicit_top_p_is_preserved(self):
        """When user explicitly sets top_p, it should be preserved."""
        config = AWSBedrockConfig(top_p=0.9)
        assert config.top_p == 0.9

    def test_get_model_config_excludes_top_p_when_none(self):
        """get_model_config should not include top_p when it is None."""
        config = AWSBedrockConfig()
        model_config = config.get_model_config()
        assert "top_p" not in model_config

    def test_get_model_config_includes_top_p_when_set(self):
        """get_model_config should include top_p when explicitly set."""
        config = AWSBedrockConfig(top_p=0.95)
        model_config = config.get_model_config()
        assert model_config["top_p"] == 0.95

    def test_temperature_always_included(self):
        """temperature should always be in model config."""
        config = AWSBedrockConfig(temperature=0.5)
        model_config = config.get_model_config()
        assert model_config["temperature"] == 0.5


# ===========================================================================
# AWSBedrockLLM — _build_inference_config
# ===========================================================================

class TestBuildInferenceConfig:
    """Test the _build_inference_config helper method."""

    @patch("mem0.llms.aws_bedrock.boto3")
    def test_inference_config_without_top_p(self, mock_boto3):
        """When top_p is None, inferenceConfig should not include topP."""
        mock_boto3.client.return_value = MagicMock()

        from mem0.llms.aws_bedrock import AWSBedrockLLM

        config = AWSBedrockConfig(
            model="anthropic.claude-sonnet-4-5-20250514-v1:0",
            temperature=0.1,
        )

        with patch.object(AWSBedrockLLM, '_test_connection'):
            llm = AWSBedrockLLM(config)

        inference_config = llm._build_inference_config()
        assert "temperature" in inference_config
        assert "maxTokens" in inference_config
        assert "topP" not in inference_config

    @patch("mem0.llms.aws_bedrock.boto3")
    def test_inference_config_with_top_p(self, mock_boto3):
        """When top_p is explicitly set, inferenceConfig should include topP."""
        mock_boto3.client.return_value = MagicMock()

        from mem0.llms.aws_bedrock import AWSBedrockLLM

        config = AWSBedrockConfig(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
            temperature=0.1,
            top_p=0.9,
        )

        with patch.object(AWSBedrockLLM, '_test_connection'):
            llm = AWSBedrockLLM(config)

        inference_config = llm._build_inference_config()
        assert inference_config["topP"] == 0.9
        assert inference_config["temperature"] == 0.1

    @patch("mem0.llms.aws_bedrock.boto3")
    def test_inference_config_custom_max_tokens(self, mock_boto3):
        """max_tokens override should be respected."""
        mock_boto3.client.return_value = MagicMock()

        from mem0.llms.aws_bedrock import AWSBedrockLLM

        config = AWSBedrockConfig(
            model="anthropic.claude-3-5-sonnet-20240620-v1:0",
        )

        with patch.object(AWSBedrockLLM, '_test_connection'):
            llm = AWSBedrockLLM(config)

        inference_config = llm._build_inference_config(max_tokens=5000)
        assert inference_config["maxTokens"] == 5000
