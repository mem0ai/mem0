import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class TurbopufferConfig(BaseModel):
    """Configuration for Turbopuffer vector database."""

    collection_name: str = Field("mem0", description="Name of the namespace/collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    client: Optional[Any] = Field(None, description="Existing Turbopuffer Namespace instance")
    api_key: Optional[str] = Field(None, description="API key for Turbopuffer")
    api_base_url: Optional[str] = Field(
        "https://gcp-us-central1.turbopuffer.com",
        description="Base URL for Turbopuffer API"
    )
    distance_metric: str = Field(
        "cosine_distance",
        description="Distance metric for vector similarity (cosine_distance or euclidean_distance)"
    )
    batch_size: int = Field(100, description="Batch size for operations")
    extra_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional parameters for Turbopuffer client"
    )

    @model_validator(mode="before")
    @classmethod
    def check_api_key_or_client(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        api_key, client = values.get("api_key"), values.get("client")
        if not api_key and not client and "TURBOPUFFER_API_KEY" not in os.environ:
            raise ValueError(
                "Either 'api_key' or 'client' must be provided, or TURBOPUFFER_API_KEY environment variable must be set."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_distance_metric(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        valid_metrics = {"cosine_distance", "euclidean_distance"}
        if values.get("distance_metric") not in valid_metrics:
            raise ValueError(
                f"Invalid distance_metric. Must be one of: {', '.join(valid_metrics)}"
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Allowed fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = {
        "arbitrary_types_allowed": True,
    }