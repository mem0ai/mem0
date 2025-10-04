"""Reranker configuration classes."""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from .base import BaseRerankerConfig
from .aws_bedrock import AWSBedrockRerankerConfig


class RerankerConfig(BaseModel):
    """Configuration for reranker."""
    
    provider: Optional[str] = Field(
        default=None, 
        description="Reranker provider (e.g., 'aws_bedrock', 'cohere', 'sentence_transformer')"
    )
    config: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Provider-specific reranker configuration"
    )
    
    model_config = {"extra": "forbid"}


__all__ = ["BaseRerankerConfig", "AWSBedrockRerankerConfig", "RerankerConfig"]
