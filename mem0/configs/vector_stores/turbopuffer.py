import os
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TurbopufferConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the namespace/collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    api_key: Optional[str] = Field(None, description="API key for Turbopuffer")
    region: str = Field("gcp-us-central1", description="Turbopuffer region (e.g., 'gcp-us-central1', 'aws-us-west-2')")
    distance_metric: str = Field(
        "cosine_distance",
        description="Distance metric for vector similarity ('cosine_distance' or 'euclidean_squared')",
    )
    batch_size: int = Field(100, description="Batch size for bulk operations")
    extra_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional parameters for Turbopuffer client",
    )

    @model_validator(mode="before")
    @classmethod
    def check_api_key(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        api_key = values.get("api_key")
        if not api_key and "TURBOPUFFER_API_KEY" not in os.environ:
            raise ValueError(
                "Either 'api_key' must be provided or TURBOPUFFER_API_KEY environment variable must be set."
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
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
