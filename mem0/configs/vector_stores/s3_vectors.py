from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class S3VectorsConfig(BaseModel):
    vector_bucket_name: str = Field(description="Name of the S3 Vector bucket")
    collection_name: str = Field("mem0", description="Name of the vector index")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    distance_metric: str = Field(
        "cosine",
        description="Distance metric for similarity search. Options: 'cosine', 'euclidean'",
    )
    region_name: Optional[str] = Field(None, description="AWS region for the S3 Vectors client")

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

    model_config = ConfigDict(arbitrary_types_allowed=True)
