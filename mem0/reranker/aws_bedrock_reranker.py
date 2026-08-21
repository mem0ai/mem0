import logging
import os
from typing import Any, Dict, List, Optional

from mem0.reranker.base import BaseReranker

try:
    import boto3

    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

logger = logging.getLogger(__name__)


class AWSBedrockReranker(BaseReranker):
    """AWS Bedrock-based reranker implementation.

    Calls the Bedrock Agent Runtime `Rerank` API, a distinct service from
    `bedrock-runtime` (used by the AWS Bedrock LLM/embedding providers) that
    exposes both the Cohere Rerank and Amazon Rerank foundation models
    through one interface.
    """

    def __init__(self, config):
        """
        Initialize AWS Bedrock reranker.

        Args:
            config: AWSBedrockRerankerConfig object with configuration parameters
        """
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 is required for AWSBedrockReranker. Install with: pip install boto3")

        self.config = config

        aws_region = config.aws_region or os.getenv("AWS_REGION", "us-west-2")
        aws_access_key = config.aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = config.aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = config.aws_session_token or os.getenv("AWS_SESSION_TOKEN")

        self.client = boto3.client(
            "bedrock-agent-runtime",
            region_name=aws_region,
            aws_access_key_id=aws_access_key or None,
            aws_secret_access_key=aws_secret_key or None,
            aws_session_token=aws_session_token or None,
        )

        self.model_arn = self._resolve_model_arn(config.model, aws_region)

    @staticmethod
    def _resolve_model_arn(model: str, aws_region: str) -> str:
        """Bedrock's Rerank API addresses models by ARN, not the bare 'provider.model' id
        the LLM/embedding providers use, so a short id is expanded to the region-scoped
        foundation-model ARN. A caller-supplied ARN is passed through unchanged.
        """
        if model.startswith("arn:aws"):
            return model
        return f"arn:aws:bedrock:{aws_region}::foundation-model/{model}"

    @staticmethod
    def _extract_text(doc: Dict[str, Any]) -> str:
        if "memory" in doc:
            return doc["memory"]
        if "text" in doc:
            return doc["text"]
        if "content" in doc:
            return doc["content"]
        return str(doc)

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using the AWS Bedrock Rerank API.

        Args:
            query: The search query
            documents: List of documents to rerank
            top_k: Number of top documents to return

        Returns:
            List of reranked documents with rerank_score
        """
        if not documents:
            return documents

        sources = [
            {
                "inlineDocumentSource": {
                    "textDocument": {"text": self._extract_text(doc)},
                    "type": "TEXT",
                },
                "type": "INLINE",
            }
            for doc in documents
        ]

        try:
            response = self.client.rerank(
                queries=[{"textQuery": {"text": query}, "type": "TEXT"}],
                sources=sources,
                rerankingConfiguration={
                    "type": "BEDROCK_RERANKING_MODEL",
                    "bedrockRerankingConfiguration": {
                        "modelConfiguration": {"modelArn": self.model_arn},
                        "numberOfResults": top_k or self.config.top_k or len(documents),
                    },
                },
            )

            reranked_docs = []
            for result in response["results"]:
                original_doc = documents[result["index"]].copy()
                original_doc["rerank_score"] = result["relevanceScore"]
                reranked_docs.append(original_doc)

            return reranked_docs

        except Exception as e:
            # Fallback to original order if reranking fails
            logger.warning("AWS Bedrock reranking failed, falling back to original order: %s", e)
            for doc in documents:
                doc["rerank_score"] = 0.0
            final_top_k = top_k or self.config.top_k
            return documents[:final_top_k] if final_top_k else documents
