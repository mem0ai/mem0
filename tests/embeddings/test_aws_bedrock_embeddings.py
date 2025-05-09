import json
from io import BytesIO
from unittest.mock import Mock, patch

import numpy as np
import pytest

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.aws_bedrock import AWSBedrockEmbedding


@pytest.fixture
def mock_bedrock_client():
    with patch("boto3.client") as mock_boto3_client:
        mock_client = Mock()
        mock_boto3_client.return_value = mock_client
        yield mock_client


def test_init_default_model(mock_bedrock_client):
    """Test initialization with default model."""
    config = BaseEmbedderConfig()
    embedder = AWSBedrockEmbedding(config)
    
    assert embedder.config.model == "amazon.titan-embed-text-v1"
    assert mock_bedrock_client is embedder.client


def test_init_custom_model(mock_bedrock_client):
    """Test initialization with custom model."""
    config = BaseEmbedderConfig(model="cohere.embed-multilingual-v3")
    embedder = AWSBedrockEmbedding(config)
    
    assert embedder.config.model == "cohere.embed-multilingual-v3"


def test_normalize_vector():
    """Test vector normalization function."""
    embedder = AWSBedrockEmbedding()
    vector = [3.0, 4.0]
    normalized = embedder._normalize_vector(vector)
    
    # Expected norm is 5.0, so normalized vector should be [0.6, 0.8]
    assert np.isclose(normalized[0], 0.6)
    assert np.isclose(normalized[1], 0.8)


def test_embed_amazon_model(mock_bedrock_client):
    """Test embedding with Amazon model."""
    config = BaseEmbedderConfig(model="amazon.titan-embed-text-v1")
    embedder = AWSBedrockEmbedding(config)
    
    # Mock response
    mock_body = BytesIO(json.dumps({"embedding": [0.1, 0.2, 0.3]}).encode())
    mock_response = {"body": mock_body}
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    result = embedder.embed("Hello world")
    
    # Verify the correct request was made
    mock_bedrock_client.invoke_model.assert_called_once_with(
        body=json.dumps({"inputText": "Hello world"}),
        modelId="amazon.titan-embed-text-v1",
        accept="application/json",
        contentType="application/json",
    )
    
    assert result == [0.1, 0.2, 0.3]


def test_embed_cohere_model(mock_bedrock_client):
    """Test embedding with Cohere model."""
    config = BaseEmbedderConfig(model="cohere.embed-multilingual-v3")
    embedder = AWSBedrockEmbedding(config)
    
    # Mock response
    mock_body = BytesIO(json.dumps({"embeddings": [[0.4, 0.5, 0.6]]}).encode())
    mock_response = {"body": mock_body}
    mock_bedrock_client.invoke_model.return_value = mock_response
    
    result = embedder.embed("Test embedding")
    
    # Verify the correct request was made
    mock_bedrock_client.invoke_model.assert_called_once_with(
        body=json.dumps({"input_type": "search_document", "texts": ["Test embedding"]}),
        modelId="cohere.embed-multilingual-v3",
        accept="application/json",
        contentType="application/json",
    )
    
    assert result == [0.4, 0.5, 0.6]


def test_embed_error_handling(mock_bedrock_client):
    """Test error handling during embedding."""
    embedder = AWSBedrockEmbedding()
    
    # Simulate an error
    mock_bedrock_client.invoke_model.side_effect = Exception("API error")
    
    with pytest.raises(ValueError) as excinfo:
        embedder.embed("Error test")
    
    assert "Error getting embedding from AWS Bedrock" in str(excinfo.value)
