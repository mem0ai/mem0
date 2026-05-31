from typing import Optional
from pydantic import BaseModel, Field


class BaseRerankerConfig(BaseModel):
    """
    Base configuration for rerankers with only common parameters.
    Provider-specific configurations should be handled by separate config classes.

    This class contains only the parameters that are common across all reranker providers.
    For provider-specific parameters, use the appropriate provider config class.
    """

    provider: Optional[str] = Field(default=None, description="The reranker provider to use")
    model: Optional[str] = Field(default=None, description="The reranker model to use")
    api_key: Optional[str] = Field(default=None, description="The API key for the reranker service")
    top_k: Optional[int] = Field(default=None, description="Maximum number of documents to return after reranking")
