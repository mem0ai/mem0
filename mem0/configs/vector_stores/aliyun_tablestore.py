from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator

class AliyunTableStoreConfig(BaseModel):
    endpoint: str = Field(description="endpoint of tablestore")
    instance_name: str = Field(description="instance_name of tablestore")
    access_key_id: str = Field(description="access_key_id of tablestore")
    access_key_secret: str = Field(description="access_key_secret of tablestore")
    vector_dimension: int = Field(1536, description="dimension of vector")
    sts_token: Optional[str] = Field(None, description="sts_token of tablestore")
    collection_name: Optional[str] = Field("mem0", description="name of the collection")
    search_index_name: Optional[str] = Field("mem0_search_index", description="index name")
    text_field: Optional[str] = Field("text", description="name of the text in table field")
    embedding_field: Optional[str] = Field("embedding", description="name of the embedding field")
    vector_metric_type: Optional[str] = Field("VM_COSINE", description="metric type for vector")

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
