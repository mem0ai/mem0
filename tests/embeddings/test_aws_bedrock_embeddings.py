from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.aws_bedrock import AWSBedrockEmbedding


@pytest.fixture
def mock_boto3_client():
    with patch("mem0.embeddings.aws_bedrock.boto3.client") as mock_client:
        mock_client.return_value = Mock()
        yield mock_client


def test_session_token_from_config_is_passed_to_client(mock_boto3_client):
    """A session token supplied via config must reach the bedrock-runtime client.

    Temporary credentials (STS / assume-role) require a session token; the LLM
    Bedrock provider already honors it, so the embedding provider should too.
    """
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(
            model="amazon.titan-embed-text-v2:0",
            aws_access_key_id="AKIA_TEST",
            aws_secret_access_key="SECRET_TEST",
            aws_session_token="SESSION_TOKEN_TEST",
            aws_region="eu-central-1",
        )
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] == "SESSION_TOKEN_TEST"
    assert kwargs["aws_access_key_id"] == "AKIA_TEST"
    assert kwargs["aws_secret_access_key"] == "SECRET_TEST"
    assert kwargs["region_name"] == "eu-central-1"


def test_session_token_falls_back_to_env(mock_boto3_client):
    """When config doesn't set a session token, the env var is still used."""
    with patch.dict(
        "mem0.embeddings.aws_bedrock.os.environ",
        {"AWS_SESSION_TOKEN": "ENV_SESSION_TOKEN"},
        clear=True,
    ):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0")
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] == "ENV_SESSION_TOKEN"


def test_no_session_token_passes_none(mock_boto3_client):
    """Without a token in config or env, the client receives None (unchanged)."""
    with patch("mem0.embeddings.aws_bedrock.os.environ", {}):
        config = BaseEmbedderConfig(model="amazon.titan-embed-text-v2:0")
        AWSBedrockEmbedding(config)

    _, kwargs = mock_boto3_client.call_args
    assert kwargs["aws_session_token"] is None
