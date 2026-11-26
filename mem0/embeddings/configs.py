from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EmbedderConfig(BaseModel):
    provider: str = Field(
        description="Provider of the embedding model (e.g., 'ollama', 'openai')",
        default="openai",
    )
    config: Optional[dict] = Field(description="Configuration for the specific embedding model", default={})

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if v is None:
            # Normalize an explicit None (the field is Optional[dict]) to the
            # default empty dict, matching VectorStoreConfig's behavior.
            return {}
        if provider in [
            "openai",
            "ollama",
            "huggingface",
            "azure_openai",
            "gemini",
            "vertexai",
            "together",
            "lmstudio",
            "langchain",
            "aws_bedrock",
            "fastembed",
        ]:
            return v
        else:
            raise ValueError(f"Unsupported embedding provider: {provider}")
