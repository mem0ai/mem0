from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValkeyConfig(BaseModel):
    """Configuration for Valkey vector store."""

    valkey_url: str = Field(..., description="Valkey server URL (e.g., redis://localhost:6379)")
    collection_name: str = Field(..., description="Name of the index / collection")
    embedding_model_dims: int = Field(..., description="Dimensions of the embedding model")
    timezone: str = Field("UTC", description="Timezone for timestamp handling")
    index_type: str = Field("hnsw", description="Index type: 'hnsw' (default) or 'flat'")
    hnsw_m: int = Field(16, description="HNSW: number of connections per layer")
    hnsw_ef_construction: int = Field(200, description="HNSW: search width during index construction")
    hnsw_ef_runtime: int = Field(10, description="HNSW: search width during queries")

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

    model_config = ConfigDict(arbitrary_types_allowed=False)
