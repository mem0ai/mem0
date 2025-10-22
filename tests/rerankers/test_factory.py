"""Tests for reranker factory."""

import pytest
from unittest.mock import patch

from mem0.utils.factory import RerankerFactory
from mem0.configs.rerankers.aws_bedrock import AWSBedrockRerankerConfig


class TestRerankerFactory:
    """Test cases for RerankerFactory."""

    @patch("mem0.reranker.aws_bedrock.AWSBedrockReranker")
    def test_create_aws_bedrock_reranker(self, mock_reranker_class):
        """Test creating AWS Bedrock reranker."""
        mock_instance = mock_reranker_class.return_value

        config = {"model": "cohere.rerank-v3-5:0", "region": "us-west-2"}

        result = RerankerFactory.create("aws_bedrock", config)

        assert result == mock_instance
        mock_reranker_class.assert_called_once_with(config)

    @patch("mem0.reranker.aws_bedrock.AWSBedrockReranker")
    def test_create_with_config_object(self, mock_reranker_class):
        """Test creating reranker with config object."""
        mock_instance = mock_reranker_class.return_value

        config = AWSBedrockRerankerConfig(model="cohere.rerank-v3-5:0", region="us-west-2")

        result = RerankerFactory.create("aws_bedrock", config)

        assert result == mock_instance
        # Should convert config object to dict
        mock_reranker_class.assert_called_once_with(config.to_dict())

    def test_create_unsupported_provider(self):
        """Test creating reranker with unsupported provider."""
        with pytest.raises(ValueError, match="Unsupported reranker provider"):
            RerankerFactory.create("unsupported_provider", {})

    @patch("mem0.reranker.aws_bedrock.AWSBedrockReranker")
    def test_create_with_none_config(self, mock_reranker_class):
        """Test creating reranker with None config."""
        mock_instance = mock_reranker_class.return_value

        result = RerankerFactory.create("aws_bedrock", None)

        assert result == mock_instance
        mock_reranker_class.assert_called_once_with({})

    @patch("importlib.import_module")
    def test_import_error(self, mock_import_module):
        """Test handling of import errors."""
        mock_import_module.side_effect = ImportError("Module not found")

        with pytest.raises(ImportError, match="Could not import reranker"):
            RerankerFactory.create("aws_bedrock", {})
