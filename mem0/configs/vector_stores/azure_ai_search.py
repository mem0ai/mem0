from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class AzureAISearchConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    service_name: str = Field(None, description="Azure Cognitive Search service name")
    api_key: str = Field(None, description="API key for the Azure Cognitive Search service")
    embedding_model_dims: int = Field(None, description="Dimension of the embedding vector")
    use_compression: bool = Field(False, description="Whether to use scalar quantization vector compression.")

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
