from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class LLMRerankerConfig(BaseRerankerConfig):
    """
    Configuration for LLM-based reranker.
    
    Attributes:
        model (str): LLM model to use for reranking. Defaults to "gpt-4o-mini".
        api_key (str): API key for the LLM provider.
        provider (str): LLM provider. Defaults to "openai".
        top_k (int): Number of top documents to return after reranking.
        temperature (float): Temperature for LLM generation. Defaults to 0.0 for deterministic scoring.
        max_tokens (int): Maximum tokens for LLM response. Defaults to 100.
        scoring_prompt (str): Custom prompt template for scoring documents.
    """
    
    model: str = Field(
        default="gpt-4o-mini",
        description="LLM model to use for reranking"
    )
    api_key: Optional[str] = Field(
        default=None,
        description="API key for the LLM provider"
    )
    provider: str = Field(
        default="openai",
        description="LLM provider (openai, anthropic, etc.)"
    )
    top_k: Optional[int] = Field(
        default=None,
        description="Number of top documents to return after reranking"
    )
    temperature: float = Field(
        default=0.0,
        description="Temperature for LLM generation"
    )
    max_tokens: int = Field(
        default=100,
        description="Maximum tokens for LLM response"
    )
    scoring_prompt: Optional[str] = Field(
        default=None,
        description="Custom prompt template for scoring documents"
    )
