from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CosVectorsConfig(BaseModel):
    bucket_name: str = Field(description="Name of the COS Vectors bucket")
    collection_name: str = Field("mem0", description="Name of the COS Vectors index")
    region: str = Field(description="Tencent Cloud region of the COS Vectors bucket")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    secret_id: str = Field(description="Secret ID for Tencent Cloud")
    secret_key: str = Field(description="Secret Key for Tencent Cloud")
    token: Optional[str] = Field(None, description="Token for Tencent Cloud")
    distance_metric: str = Field(
        "cosine",
        description="Distance metric for similarity search. Options: 'cosine', 'euclidean'",
    )
    internal_access: bool = Field(
        False, description="Whether to use internal access to COS Vectors"
    )

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
