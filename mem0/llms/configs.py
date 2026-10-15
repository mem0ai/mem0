from typing import Optional

from pydantic import BaseModel, Field, field_validator


_BUILTIN_LLM_PROVIDERS = (
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
        try:
            from mem0.utils.factory import LlmFactory

            supported = set(_BUILTIN_LLM_PROVIDERS) | set(LlmFactory.get_supported_providers())
        except ImportError:
            supported = set(_BUILTIN_LLM_PROVIDERS)
        if provider in supported:
            return v
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
