from unittest.mock import MagicMock, patch

from mem0.configs.llms.aws_bedrock import AWSBedrockConfig


class TestAWSBedrockTimeout:
    """Test boto3 timeout configuration for AWS Bedrock."""

    def test_default_timeouts_are_none(self):
        config = AWSBedrockConfig()
        assert config.read_timeout is None
        assert config.connect_timeout is None

    def test_custom_timeouts(self):
        config = AWSBedrockConfig(read_timeout=300, connect_timeout=10)
        assert config.read_timeout == 300
        assert config.connect_timeout == 10

    @patch("mem0.llms.aws_bedrock.boto3")
    def test_timeout_passed_to_boto3_client(self, mock_boto3):
        mock_boto3.client.return_value = MagicMock()
        from mem0.llms.aws_bedrock import AWSBedrockLLM

        config = AWSBedrockConfig(read_timeout=600, connect_timeout=30)

        with patch.object(AWSBedrockLLM, "_test_connection"):
            with patch.object(AWSBedrockLLM, "_initialize_provider_settings"):
                llm = AWSBedrockLLM(config)

        call_kwargs = mock_boto3.client.call_args
        boto_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert boto_config is not None
        assert boto_config.read_timeout == 600
        assert boto_config.connect_timeout == 30

    @patch("mem0.llms.aws_bedrock.boto3")
    def test_no_timeout_no_boto_config(self, mock_boto3):
        mock_boto3.client.return_value = MagicMock()
        from mem0.llms.aws_bedrock import AWSBedrockLLM

        config = AWSBedrockConfig()

        with patch.object(AWSBedrockLLM, "_test_connection"):
            with patch.object(AWSBedrockLLM, "_initialize_provider_settings"):
                llm = AWSBedrockLLM(config)

        call_kwargs = mock_boto3.client.call_args
        boto_config = call_kwargs.kwargs.get("config") or call_kwargs[1].get("config")
        assert boto_config is None
