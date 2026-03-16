from typing import Any, Dict, Optional
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
        llm (dict): Optional nested LLM configuration dict with ``provider`` and ``config``
            keys.  When provided, ``provider`` and all fields inside ``config`` (e.g.
            ``ollama_base_url``, ``model``) take precedence over the top-level fields.

            Example::

                {
                    "provider": "ollama",
                    "config": {
                        "model": "dengcao/Qwen3-Reranker-0.6B:F16",
                        "ollama_base_url": "http://localhost:11434"
                    }
                }
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
    llm: Optional[Dict[str, Any]] = Field(
        default=None,
        description=(
            "Nested LLM configuration with 'provider' and 'config' keys. "
            "Overrides top-level provider/model/api_key when provided."
        ),
    )
