import json
from io import BytesIO
from unittest.mock import Mock, patch

import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.aws_bedrock import AWSBedrockEmbedding


@pytest.fixture
def mock_boto3_client():
    with patch("mem0.embeddings.aws_bedrock.boto3") as mock_boto3:
        mock_client = Mock()
        mock_boto3.client.return_value = mock_client
        yield mock_client


def make_bedrock_response(body_dict):
    body_bytes = json.dumps(body_dict).encode()
    mock_response = Mock()
    mock_response.get.return_value = BytesIO(body_bytes)
    return mock_response


def test_embed_amazon_titan(mock_boto3_client):
    config = BaseEmbedderConfig(model="amazon.titan-embed-text-v1", aws_region="us-east-1")
    embedder = AWSBedrockEmbedding(config)

    mock_boto3_client.invoke_model.return_value = make_bedrock_response({"embedding": [0.1, 0.2, 0.3]})

    result = embedder.embed("hello world")

    assert result == [0.1, 0.2, 0.3]


def test_embed_batch_cohere_single_call(mock_boto3_client):
    config = BaseEmbedderConfig(model="cohere.embed-english-v3", aws_region="us-east-1")
    embedder = AWSBedrockEmbedding(config)

    mock_boto3_client.invoke_model.return_value = make_bedrock_response(
        {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    )

    result = embedder.embed_batch(["first", "second"])

    mock_boto3_client.invoke_model.assert_called_once()
    call_body = json.loads(mock_boto3_client.invoke_model.call_args.kwargs["body"])
    assert call_body["texts"] == ["first", "second"]
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_cohere_chunks_at_96(mock_boto3_client):
    config = BaseEmbedderConfig(model="cohere.embed-english-v3", aws_region="us-east-1")
    embedder = AWSBedrockEmbedding(config)

    mock_boto3_client.invoke_model.side_effect = [
        make_bedrock_response({"embeddings": [[float(i)] for i in range(96)]}),
        make_bedrock_response({"embeddings": [[float(i)] for i in range(4)]}),
    ]

    result = embedder.embed_batch([f"text {i}" for i in range(100)])

    assert mock_boto3_client.invoke_model.call_count == 2
    assert len(result) == 100


def test_embed_batch_titan_falls_back_to_serial(mock_boto3_client):
    config = BaseEmbedderConfig(model="amazon.titan-embed-text-v1", aws_region="us-east-1")
    embedder = AWSBedrockEmbedding(config)

    mock_boto3_client.invoke_model.side_effect = [
        make_bedrock_response({"embedding": [0.1, 0.2]}),
        make_bedrock_response({"embedding": [0.3, 0.4]}),
    ]

    result = embedder.embed_batch(["first", "second"])

    assert mock_boto3_client.invoke_model.call_count == 2
    assert result == [[0.1, 0.2], [0.3, 0.4]]


def test_embed_batch_cohere_raises_on_api_error(mock_boto3_client):
    config = BaseEmbedderConfig(model="cohere.embed-english-v3", aws_region="us-east-1")
    embedder = AWSBedrockEmbedding(config)

    mock_boto3_client.invoke_model.side_effect = Exception("throttled")

    with pytest.raises(ValueError, match="Error getting batch embedding from AWS Bedrock"):
        embedder.embed_batch(["text"])
