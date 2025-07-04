from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class BaiduDBConfig(BaseModel):
    endpoint: str = Field("http://localhost:8287", description="Endpoint URL for Baidu VectorDB")
    account: str = Field("root", description="Account for Baidu VectorDB")
    api_key: str = Field(None, description="API Key for Baidu VectorDB")
    database_name: str = Field("mem0", description="Name of the database")
    table_name: str = Field("mem0", description="Name of the table")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    metric_type: str = Field("L2", description="Metric type for similarity search")

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
