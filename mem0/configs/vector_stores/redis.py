from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


# TODO: Upgrade to latest pydantic version
class RedisDBConfig(BaseModel):
    redis_url: str = Field(..., description="Redis URL")
    collection_name: str = Field("mem0", description="Collection name")
    embedding_model_dims: int = Field(1536, description="Embedding model dimensions")

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }
