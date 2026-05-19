from typing import Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LogosDBConfig(BaseModel):
    collection_name: str = Field("mem0", description="Default collection name")
    path: str = Field("/tmp/logosdb", description="Root directory for collection sub-directories")
    embedding_model_dims: int = Field(1536, description="Embedding vector dimension")
    distance_metric: str = Field(
        "cosine",
        description="Distance metric: 'cosine' (default) or 'l2'",
    )
    max_elements: int = Field(1_000_000, description="HNSW index capacity per collection")
    ef_construction: int = Field(200, description="HNSW build-time ef parameter")
    M: int = Field(16, description="HNSW graph out-degree")
    ef_search: int = Field(50, description="HNSW query-time ef parameter")

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict) -> Dict:
        allowed = set(cls.model_fields.keys())
        extra = set(values.keys()) - allowed
        if extra:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra)}. "
                f"Allowed fields: {', '.join(allowed)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
