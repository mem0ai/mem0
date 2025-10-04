"""AWS Bedrock reranker implementation using Cohere models."""

import json
import logging
from typing import Any, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError

from .base import BaseReranker, RerankerResult

logger = logging.getLogger(__name__)


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
                - top_n: Number of results to return (optional, defaults to 10)
        """
        super().__init__(config)
        
        self.model_id = config.get("model", "cohere.rerank-v3-5:0")
        self.region = config.get("region", "us-west-2")
        self.top_n = config.get("top_n", 10)
        
        # Initialize Bedrock client
        try:
            if "access_key_id" in config and "secret_access_key" in config:
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region,
                    aws_access_key_id=config["access_key_id"],
                    aws_secret_access_key=config["secret_access_key"]
                )
            else:
                # Use default credentials chain
                self.bedrock_client = boto3.client(
                    "bedrock-runtime",
                    region_name=self.region
                )
        except Exception as e:
            logger.error(f"Failed to initialize Bedrock client: {e}")
            raise
    
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        top_n: Optional[int] = None
    ) -> List[RerankerResult]:
        """Rerank documents using AWS Bedrock Cohere model.
        
        Args:
            query: The search query
            documents: List of documents to rerank
            top_n: Number of top results to return (if None, uses config default)
            
        Returns:
            List of reranked results with scores
        """
        if not documents:
            return []
        
        # Use provided top_n or config default
        effective_top_n = top_n or self.top_n
        
        # Prepare documents for reranking
        document_texts = self._prepare_documents(documents)
        
        # Prepare the request body for Bedrock
        request_body = {
            "query": query,
            "documents": document_texts,
            "top_n": min(effective_top_n, len(documents))
        }
        
        try:
            # Invoke the Bedrock model
            response = self.bedrock_client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(request_body),
                contentType="application/json"
            )
            
            # Parse the response
            response_body = json.loads(response["body"].read())
            
            # Extract results
            results = response_body.get("results", [])
            
            # Convert to RerankerResult objects
            reranked_results = []
            for i, result in enumerate(results):
                doc_index = result.get("index", i)
                if doc_index < len(documents):
                    reranked_results.append(RerankerResult(
                        id=documents[doc_index].get("id", f"doc_{doc_index}"),
                        score=result.get("relevance_score", 0.0),
                        rank=i + 1,
                        content=documents[doc_index].get("memory", documents[doc_index].get("data", ""))
                    ))
            
            return reranked_results
            
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

