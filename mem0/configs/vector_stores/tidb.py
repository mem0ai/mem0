from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class IndexMethod(str, Enum):
    HNSW = "hnsw"


class DistanceMetric(str, Enum):
    """
    An enumeration representing different types of distance metrics.

    - `DistanceMetric.L2`: L2 (Euclidean) distance metric.
    - `DistanceMetric.COSINE`: Cosine distance metric.
    """

    L2 = "L2"
    COSINE = "COSINE"

    def to_sql_func(self):
        """
        Converts the DistanceMetric to its corresponding SQL function name.

        Returns:
            str: The SQL function name.

        Raises:
            ValueError: If the DistanceMetric enum member is not supported.
        """
        if self == DistanceMetric.L2:
            return "VEC_L2_DISTANCE"
        elif self == DistanceMetric.COSINE:
            return "VEC_COSINE_DISTANCE"
        else:
            raise ValueError("unsupported distance metric")


class TiDBConfig(BaseModel):
    database: str = Field("test", description="Default name for the database")
    collection_name: str = Field("mem0", description="Default name for the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field("root", description="Database user. Default is root")
    password: Optional[str] = Field("", description="Database password. Default is empty string")
    host: Optional[str] = Field("localhost", description="Database host. Default is localhost")
    port: Optional[int] = Field(4000, description="Database port. Default is 4000")
    enable_ssl: Optional[bool] = Field(False, description="Enable SSL connection. Default is False")
    index_method: Optional[IndexMethod] = Field(IndexMethod.HNSW, description="Index method to use. Default is HNSW")
    distance_metric: Optional[DistanceMetric] = Field(DistanceMetric.COSINE, description="Distance metric to use. Default is COSINE")

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
