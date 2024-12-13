from enum import Enum
from typing import Any, Dict, List

from pydantic import BaseModel, Field, model_validator
from volcengine.viking_db import VikingDBService, Field, FieldType

class MetricType(str, Enum):
    """
    Metric Constant for VikingDB/ Volcengine server.
    """

    def __str__(self) -> str:
        return str(self.value)

    L2 = "L2"
    IP = "IP"
    COSINE = "COSINE"

class VikingDBConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: int = Field(2048, description="Dimensions of the embedding model")
    metric_type: str = Field("IP", description="Metric type for similarity search")
    ak: str = Field(None, description="ACCESSKEY for authentication")
    sk: str = Field(None, description="SECRETKEY for authentication")
    host: str = Field("api-vikingdb.volces.com", description="Host for VikingDB/ Volcengine server")
    region: str = Field("cn-beijing", description="Region for VikingDB server")
    


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
