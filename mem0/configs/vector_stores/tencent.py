from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TencentVectorDBConfig(BaseModel):
    url: str = Field(..., description="Tencent Vector DB connection URL")
    key: str = Field(..., description="Tencent Vector DB connection Key/Token")
    collection_name: str = Field("mem0", description="Collection name")
    embedding_model_dims: int = Field(1536, description="Dimension of dense vector")
    metric_type: str = Field("COSINE", description="Metric type. E.g. COSINE, L2, IP")
    username: str = Field("root", description="Username")
    database_name: str = Field("default", description="Database name")
    read_consistency: str = Field("EVENTUAL_CONSISTENCY", description="Read consistency level")
    timeout: int = Field(30, description="Timeout in seconds")
    shard: int = Field(1, description="Number of shards")
    replicas: int = Field(2, description="Number of replicas")
    index_type: str = Field("HNSW", description="Dense vector index type")
    index_params: Optional[Dict[str, Any]] = Field(None, description="Optional parameters dictionary for the index")
    sparse_language: str = Field("en", description="Language parameter for sparse vector BM25 encoder")

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
