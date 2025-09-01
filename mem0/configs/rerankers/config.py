from typing import Optional

from pydantic import BaseModel, Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class RerankerConfig(BaseModel):
    """Configuration for rerankers."""
    
    provider: str = Field(description="Reranker provider (e.g., 'cohere', 'sentence_transformer')", default="cohere")
    config: Optional[BaseRerankerConfig] = Field(description="Provider-specific reranker configuration", default=None)
    
    model_config = {"extra": "forbid"}