import os
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TopKConfig(BaseModel):
    collection_name: str = Field(..., description="Name of the TopK collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    api_key: Optional[str] = Field(None, description="TopK API key (env: TOPK_API_KEY)")
    region: Optional[str] = Field(None, description="TopK region (env: TOPK_REGION)")
    host: Optional[str] = Field(None, description="TopK host (env: TOPK_HOST); defaults to topk.io")
    https: Optional[bool] = Field(None, description="TopK HTTPS (env: TOPK_HTTPS); defaults to True")
    distance_metric: str = Field("cosine", description="Distance metric: cosine | euclidean | dot")
    batch_size: int = Field(100, description="Batch size for upsert operations")
    partition: Optional[str] = Field(None, description="Partition name to scope all data operations (for multi-tenant use)")

    @model_validator(mode="before")
    @classmethod
    def check_api_key(cls, values):
        if not values.get("api_key") and "TOPK_API_KEY" not in os.environ:
            raise ValueError(
                "Either 'api_key' must be provided or TOPK_API_KEY environment variable must be set."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def check_region(cls, values):
        if not values.get("region") and "TOPK_REGION" not in os.environ:
            raise ValueError(
                "Either 'region' must be provided or TOPK_REGION environment variable must be set."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values):
        allowed = set(cls.model_fields.keys())
        extra = set(values.keys()) - allowed
        if extra:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra)}. "
                f"Allowed fields: {', '.join(allowed)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
