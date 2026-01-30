from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TOSVectorsConfig(BaseModel):
    vector_bucket_name: str = Field("mem0", description="Name of the TOS Vectors bucket")
    collection_name: str = Field("mem0", description="Name of the collection/index")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    endpoint: str = Field("https://tosvectors-cn-beijing.volces.com", description="Endpoint URL for TOS Vectors")
    region: str = Field("cn-beijing", description="Region for TOS Vectors")
    distance_metric: str = Field("cosine", description="Distance metric for similarity search (cosine or euclidean)")

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
