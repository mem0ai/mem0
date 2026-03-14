from typing import Any, Dict, Optional
from pydantic import Field, model_validator

from mem0.configs.rerankers.base import BaseRerankerConfig


class LLMRerankerConfig(BaseRerankerConfig):
    """
    Configuration for LLM-based reranker.
    
    Supports two configuration styles:

    1. Flat config (provider/model at top level):
       {"provider": "openai", "model": "gpt-4o-mini", "api_key": "..."}

    2. Nested config (provider/model inside "llm" dict):
       {"llm": {"provider": "ollama", "config": {"model": "...", "ollama_base_url": "..."}}}

    Attributes:
        model (str): LLM model to use for reranking. Defaults to "gpt-4o-mini".
        api_key (str): API key for the LLM provider.
        provider (str): LLM provider. Defaults to "openai".
        top_k (int): Number of top documents to return after reranking.
        temperature (float): Temperature for LLM generation. Defaults to 0.0 for deterministic scoring.
        max_tokens (int): Maximum tokens for LLM response. Defaults to 100.
        scoring_prompt (str): Custom prompt template for scoring documents.
        llm (dict): Nested LLM configuration with "provider" and "config" keys.
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
        description="Nested LLM configuration with 'provider' and 'config' keys"
    )

    @model_validator(mode="before")
    @classmethod
    def extract_nested_llm_config(cls, values):
        """Extract provider, model, and other settings from nested 'llm' config if present."""
        if not isinstance(values, dict):
            return values

        llm = values.get("llm")
        if llm and isinstance(llm, dict):
            nested_provider = llm.get("provider")
            nested_config = llm.get("config", {})

            # Only override if not explicitly set at the top level
            if nested_provider and values.get("provider", "openai") == "openai":
                values["provider"] = nested_provider
            if nested_config.get("model") and values.get("model", "gpt-4o-mini") == "gpt-4o-mini":
                values["model"] = nested_config["model"]
            if nested_config.get("api_key") and not values.get("api_key"):
                values["api_key"] = nested_config["api_key"]
            if nested_config.get("temperature") is not None and values.get("temperature", 0.0) == 0.0:
                values["temperature"] = nested_config["temperature"]
            if nested_config.get("max_tokens") and values.get("max_tokens", 100) == 100:
                values["max_tokens"] = nested_config["max_tokens"]

        return values
