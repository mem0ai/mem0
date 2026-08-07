from typing import Optional

from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class AWSBedrockRerankerConfig(BaseRerankerConfig):
    """
    Configuration for the AWS Bedrock reranker.

    Uses the Bedrock Agent Runtime Rerank API rather than the bedrock-runtime
    invoke_model/converse calls used by the LLM and embedding providers, so
    authentication is plain IAM (no api_key) and the model is addressed by a
    foundation-model ARN.
    """

    model: str = Field(
        default="cohere.rerank-v3-5:0",
        description="Bedrock rerank model ID (e.g. 'cohere.rerank-v3-5:0', 'amazon.rerank-v1:0') or a full model ARN",
    )
    aws_region: Optional[str] = Field(
        default=None, description="AWS region for the Bedrock reranking service. Falls back to the AWS_REGION env var"
    )
    aws_access_key_id: Optional[str] = Field(default=None, description="AWS access key ID for authentication")
    aws_secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key for authentication")
    aws_session_token: Optional[str] = Field(
        default=None, description="AWS session token for temporary credentials (STS / assume-role)"
    )
    top_k: Optional[int] = Field(default=None, description="Number of top documents to return after reranking")
