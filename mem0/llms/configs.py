from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LlmConfig(BaseModel):
    provider: str = Field(description="Provider of the LLM (e.g., 'ollama', 'openai')", default="openai")
    config: Optional[dict] = Field(description="Configuration for the specific LLM", default={})

    @field_validator("config")
    def validate_config(cls, v, values):
        # Lazy import avoids a circular import with mem0.configs.base (which
        # imports LlmConfig back from this module).
        from mem0.utils.factory import LlmFactory

        provider = values.data.get("provider")
        # Reference the single source of truth in LlmFactory so that providers
        # registered at runtime via LlmFactory.register_provider are also accepted.
        if provider in LlmFactory.provider_to_class:
            return v
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
