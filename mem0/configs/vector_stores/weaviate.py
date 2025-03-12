from typing import Any, ClassVar, Dict, Optional
from pydantic import BaseModel, Field, model_validator


class WeaviateConfig(BaseModel):
    from weaviate import WeaviateClient

    WeaviateClient: ClassVar[type] = WeaviateClient

    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    cluster_url: Optional[str] = Field(None, description="URL for Weaviate server")
    auth_client_secret: Optional[str] = Field(None, description="API key for Weaviate authentication")
    additional_headers: Optional[Dict[str, str]] = Field(None, description="Additional headers for requests")

    @model_validator(mode="before")
    @classmethod
    def check_connection_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        cluster_url = values.get("cluster_url")

        if not cluster_url:
            raise ValueError("'cluster_url' must be provided.")

        return values

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
