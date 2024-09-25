from enum import Enum
from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class MetricType(str, Enum):
    """
    Metric Constant for milvus/ zilliz server.
    """

    def __str__(self) -> str:
        return str(self.value)

    L2 = "L2"
    IP = "IP"
    COSINE = "COSINE"
    HAMMING = "HAMMING"
    JACCARD = "JACCARD"


class MilvusDBConfig(BaseModel):
    url: str = Field("http://localhost:19530", description="Full URL for Milvus/Zilliz server")
    token: str = Field(None, description="Token for Zilliz server / local setup defaults to None.")
    collection_name: str = Field("mem0", description="Name of the collection")
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
