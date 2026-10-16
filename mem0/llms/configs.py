from typing import Optional

from pydantic import BaseModel, Field, field_validator

# Providers supported out of the box. Must stay in sync with
# LlmFactory.provider_to_class in mem0/utils/factory.py; providers added at
# runtime via LlmFactory.register_provider() are accepted dynamically in
# validate_config() below.
BUILTIN_LLM_PROVIDERS = (
    "openai",
    "ollama",
    "anthropic",
    "groq",
    "together",
    "aws_bedrock",
    "litellm",
    "azure_openai",
    "openai_structured",
    "azure_openai_structured",
    "gemini",
    "deepseek",
    "minimax",
    "xai",
    "sarvam",
    "lmstudio",
    "vllm",
    "langchain",
)


class LlmConfig(BaseModel):
    provider: str = Field(description="Provider of the LLM (e.g., 'ollama', 'openai')", default="openai")
    config: Optional[dict] = Field(description="Configuration for the specific LLM", default={})

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider in BUILTIN_LLM_PROVIDERS:
            return v
        # Accept providers registered at runtime via LlmFactory.register_provider().
        # Imported lazily to keep the config model independent of the factory's
        # provider modules (and to avoid import cycles).
        from mem0.utils.factory import LlmFactory

        if provider in LlmFactory.provider_to_class:
            return v
        raise ValueError(f"Unsupported LLM provider: {provider}")
