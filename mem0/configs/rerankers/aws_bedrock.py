"""AWS Bedrock reranker configuration."""

from typing import Optional

from pydantic import Field

from .base import BaseRerankerConfig


class AWSBedrockRerankerConfig(BaseRerankerConfig):
    """Configuration for AWS Bedrock reranker."""
    
    provider: str = Field(default="aws_bedrock", description="Provider name")
    model: str = Field(default="cohere.rerank-v3-5:0", description="Bedrock model ID")
    region: str = Field(default="us-west-2", description="AWS region")
    access_key_id: Optional[str] = Field(default=None, description="AWS access key ID")
    secret_access_key: Optional[str] = Field(default=None, description="AWS secret access key")
    top_n: int = Field(default=5, description="Number of top results to return")
    
    model_config = {"extra": "forbid"}

