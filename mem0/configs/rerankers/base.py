"""Base reranker configuration class."""

from abc import ABC
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseRerankerConfig(BaseModel, ABC):
    """Base configuration class for rerankers."""
    
    provider: str = Field(..., description="Reranker provider name")
    top_n: int = Field(default=10, description="Number of top results to return")
    
    model_config = {"extra": "forbid"}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert config to dictionary."""
        return self.model_dump()

