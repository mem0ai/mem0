from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class CassandraDBConfig(BaseModel):
    endpoint: str = Field("http://localhost:9042", description="Endpoint URL for Cassandra Vector Search")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field(None, description="Database host. Default is localhost")
    port: Optional[int] = Field(None, description="Database port. Default is 1536")
    database_name: str = Field("mem0", description="Name of the database")
    table_name: str = Field("mem0", description="Name of the table")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")

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
