"""Tests for AWS Bedrock reranker."""

import json
import pytest
from unittest.mock import Mock, patch

from mem0.rerankers.aws_bedrock import AWSBedrockReranker
from mem0.rerankers.base import RerankerResult


class TestAWSBedrockReranker:
    """Test cases for AWS Bedrock reranker."""
    
    @pytest.fixture
    def mock_bedrock_client(self):
        """Mock AWS Bedrock client."""
        mock_client = Mock()
        mock_response = {
            "body": Mock()
        }
        mock_response["body"].read.return_value = json.dumps({
            "results": [
                {"index": 1, "relevance_score": 0.95},
                {"index": 0, "relevance_score": 0.85},
                {"index": 2, "relevance_score": 0.75}
            ]
        }).encode()
        mock_client.invoke_model.return_value = mock_response
        return mock_client
    
    @pytest.fixture
    def sample_config(self):
        """Sample configuration for AWS Bedrock reranker."""
        return {
            "model": "cohere.rerank-v3-5:0",
            "region": "us-west-2",
            "top_n": 3
        }
    
    @pytest.fixture
    def sample_documents(self):
        """Sample documents for testing."""
        return [
            {"id": "doc1", "memory": "Python programming language"},
            {"id": "doc2", "memory": "Machine learning algorithms"},
            {"id": "doc3", "memory": "Data science techniques"}
        ]
    
    @patch('boto3.client')
    def test_initialization(self, mock_boto_client, sample_config, mock_bedrock_client):
        """Test reranker initialization."""
        mock_boto_client.return_value = mock_bedrock_client
        
        reranker = AWSBedrockReranker(sample_config)
        
        assert reranker.model_id == "cohere.rerank-v3-5:0"
        assert reranker.region == "us-west-2"
        assert reranker.top_n == 3
        assert reranker.bedrock_client == mock_bedrock_client
    
    @patch('boto3.client')
    def test_rerank_success(self, mock_boto_client, sample_config, mock_bedrock_client, sample_documents):
        """Test successful reranking."""
        mock_boto_client.return_value = mock_bedrock_client
        
        reranker = AWSBedrockReranker(sample_config)
        query = "machine learning"
        
        results = reranker.rerank(query, sample_documents)
        
        # Verify Bedrock client was called correctly
        mock_bedrock_client.invoke_model.assert_called_once()
        call_args = mock_bedrock_client.invoke_model.call_args
        
        assert call_args[1]["modelId"] == "cohere.rerank-v3-5:0"
        
        # Verify request body
        request_body = json.loads(call_args[1]["body"])
        assert request_body["query"] == query
        assert len(request_body["documents"]) == 3
        assert request_body["top_n"] == 3
        
        # Verify results
        assert len(results) == 3
        assert all(isinstance(result, RerankerResult) for result in results)
        assert results[0].id == "doc2"  # Highest relevance
        assert results[0].score == 0.95
        assert results[1].id == "doc1"
        assert results[1].score == 0.85
    
    @patch('boto3.client')
    def test_rerank_with_top_n_override(self, mock_boto_client, sample_config, mock_bedrock_client, sample_documents):
        """Test reranking with custom top_n parameter."""
        mock_boto_client.return_value = mock_bedrock_client
        
        reranker = AWSBedrockReranker(sample_config)
        query = "machine learning"
        
        results = reranker.rerank(query, sample_documents, top_n=2)
        
        # Verify request body has correct top_n
        call_args = mock_bedrock_client.invoke_model.call_args
        request_body = json.loads(call_args[1]["body"])
        assert request_body["top_n"] == 2
        
        # Verify results length
        assert len(results) == 2
    
    @patch('boto3.client')
    def test_rerank_empty_documents(self, mock_boto_client, sample_config, mock_bedrock_client):
        """Test reranking with empty document list."""
        mock_boto_client.return_value = mock_bedrock_client
        
        reranker = AWSBedrockReranker(sample_config)
        query = "test query"
        
        results = reranker.rerank(query, [])
        
        # Should not call Bedrock and return empty results
        mock_bedrock_client.invoke_model.assert_not_called()
        assert len(results) == 0
    
    @patch('boto3.client')
    def test_rerank_bedrock_error(self, mock_boto_client, sample_config, mock_bedrock_client, sample_documents):
        """Test handling of Bedrock client errors."""
        from botocore.exceptions import ClientError
        
        mock_boto_client.return_value = mock_bedrock_client
        mock_bedrock_client.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ValidationException", "Message": "Invalid model"}},
            "invoke_model"
        )
        
        reranker = AWSBedrockReranker(sample_config)
        query = "test query"
        
        with pytest.raises(Exception, match="AWS Bedrock error"):
            reranker.rerank(query, sample_documents)
    
    @patch('boto3.client')
    def test_prepare_documents(self, mock_boto_client, sample_config, mock_bedrock_client):
        """Test document preparation method."""
        mock_boto_client.return_value = mock_bedrock_client
        
        reranker = AWSBedrockReranker(sample_config)
        
        documents = [
            {"id": "doc1", "memory": "Python programming"},
            {"id": "doc2", "data": "Machine learning"},
            {"id": "doc3", "content": "Data science"}
        ]
        
        texts = reranker._prepare_documents(documents)
        
        assert texts == ["Python programming", "Machine learning", "Data science"]
    
    @patch('boto3.client')
    def test_validate_model(self, mock_boto_client, sample_config, mock_bedrock_client):
        """Test model validation."""
        mock_boto_client.return_value = mock_bedrock_client
        mock_bedrock_client.list_foundation_models.return_value = {
            "modelSummaries": [
                {"modelId": "cohere.rerank-v3-5:0"},
                {"modelId": "anthropic.claude-3-sonnet-20240229-v1:0"}
            ]
        }
        
        reranker = AWSBedrockReranker(sample_config)
        
        assert reranker._validate_model() is True
        
        # Test with invalid model
        reranker.model_id = "invalid.model"
        assert reranker._validate_model() is False

