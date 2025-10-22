"""AWS Bedrock reranker implementation using Cohere models."""

import json
import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from mem0.reranker.base import BaseReranker

logger = logging.getLogger(__name__)


class RerankedResult:
    """Result object for reranked documents."""

    def __init__(self, doc_dict, score):
        self._doc = doc_dict
        self.score = score

    @property
    def id(self):
        return self._doc.get("id")

    def __getattr__(self, name):
        return self._doc.get(name)


class AWSBedrockReranker(BaseReranker):
    """AWS Bedrock reranker using Cohere models."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize AWS Bedrock reranker.

        Args:
            config: Configuration dictionary containing:
                - model: The model ID (e.g., 'cohere.rerank-v3-5:0')
                - region: AWS region (optional, defaults to us-west-2)
                - access_key_id: AWS access key (optional, uses credentials chain)
                - secret_access_key: AWS secret key (optional, uses credentials chain)
                - top_k: Number of results to return (optional, defaults to 10)
        """
        super().__init__(config)

        # Handle both dict and config object
        if hasattr(config, "model"):
            # Config object
            self.model_id = config.model
            self.region = getattr(config, "region", "us-west-2")
            self.top_k = getattr(config, "top_k", 10)
            access_key_id = getattr(config, "access_key_id", None)
            secret_access_key = getattr(config, "secret_access_key", None)
        else:
            # Dict config
            self.model_id = config.get("model", "cohere.rerank-v3-5:0")
            self.region = config.get("region", "us-west-2")
            # Support either key from user/config
            self.top_k = config.get("top_k") or 10
            access_key_id = config.get("access_key_id")
            secret_access_key = config.get("secret_access_key")

        # Initialize Bedrock client
        try:
            if access_key_id and secret_access_key:
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region,
                    aws_access_key_id=access_key_id,
                    aws_secret_access_key=secret_access_key,
                )
            else:
                # Use default credentials chain
                self.bedrock_client = boto3.client("bedrock-runtime", region_name=self.region)
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """Rerank documents using AWS Bedrock Cohere model.

        Args:
            query: The search query
            documents: List of documents to rerank
            top_k: Number of top results to return (if None, uses config default)

        Returns:
            List of reranked results with scores
        """
        if not documents:
            return []

        # Determine limits
        limit = getattr(self, "top_k", None) or len(documents)
        # Prepare documents for reranking
        document_texts = self._prepare_documents(documents)

        # Prepare the request body for Bedrock
        request_body = {"query": query, "documents": document_texts, "top_k": limit}
        if top_k is not None:
            request_body["top_k"] = min(top_k, len(documents))
            limit = request_body["top_k"]

        try:
            # Invoke the Bedrock model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id, body=json.dumps(request_body), contentType="application/json"
            )

            # Parse the response
            response_body = json.loads(response["body"].read())

            # Extract results
            results = response_body.get("results", [])

            # Create reranked results
            reranked_docs = []
            for result in results:
                original_doc = documents[result["index"]].copy()
                original_doc["rerank_score"] = result["relevance_score"]
                reranked_result = RerankedResult(original_doc, result["relevance_score"])
                reranked_docs.append(reranked_result)

            # Enforce requested limit on returned results
            return reranked_docs[:limit]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            logger.error(f"AWS Bedrock client error ({error_code}): {error_message}")
            raise Exception(f"AWS Bedrock error: {error_message}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Bedrock response: {e}")
            raise Exception("Failed to parse reranking response")

        except Exception as e:
            logger.error(f"Unexpected error during reranking: {e}")
            raise

    def _prepare_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Extract text content from documents for reranking.

        Args:
            documents: List of documents with various text fields

        Returns:
            List of text strings extracted from documents
        """
        texts = []
        for doc in documents:
            # Try different possible text fields
            text = doc.get("memory") or doc.get("data") or doc.get("content") or doc.get("text", "")
            texts.append(str(text))
        return texts

    def _validate_model(self) -> bool:
        """Validate that the model is available and accessible.

        Returns:
            True if model is accessible, False otherwise
        """
        try:
            # Try to list available models to validate access
            response = self.bedrock_client.list_foundation_models()
            model_ids = [model["modelId"] for model in response["modelSummaries"]]
            return self.model_id in model_ids
        except Exception as e:
            logger.warning(f"Could not validate model availability: {e}")
            return True  # Assume it's available if we can't check
