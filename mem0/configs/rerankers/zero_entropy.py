from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class ZeroEntropyRerankerConfig(BaseRerankerConfig):
    """
    Configuration for Zero Entropy reranker.
    
    Attributes:
        model (str): Model to use for reranking. Defaults to "zerank-1".
        api_key (str): Zero Entropy API key. If not provided, will try to read from ZERO_ENTROPY_API_KEY environment variable.
        top_k (int): Number of top documents to return after reranking.
    """
    
    model: str = Field(
        default="zerank-1",
        description="Model to use for reranking. Available models: zerank-1, zerank-1-small"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="Zero Entropy API key"
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Number of top documents to return after reranking"
    )
