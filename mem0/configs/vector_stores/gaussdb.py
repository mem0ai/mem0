from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GaussDBConfig(BaseModel):
    """Configuration for GaussDB vector database."""

    host: Optional[str] = Field(None, description="GaussDB server host")
    port: int = Field(5432, description="GaussDB server port")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    dbname: Optional[str] = Field(None, description="Database name")
    collection_name: str = Field("mem0", description="Table name used as collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    diskann: bool = Field(False, description="Create DiskANN index for ANN search")
    hnsw: bool = Field(False, description="Create HNSW index for ANN search")
    sslmode: Optional[str] = Field(None, description="SSL mode: disable/require/verify-full")
    minconn: int = Field(1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, description="Maximum number of connections in the pool")
    connection_string: Optional[str] = Field(None, description="Full DSN, overrides individual params")
    connection_pool: Optional[Any] = Field(None, description="Pre-configured connection pool object")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def check_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if values.get("connection_pool") or values.get("connection_string"):
            return values
        for field in ("host", "user", "dbname", "password"):
            if not values.get(field):
                raise ValueError(
                    f"'{field}' is required when connection_pool and connection_string are not provided"
                )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        extra_fields = set(values.keys()) - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Allowed fields: {', '.join(allowed_fields)}"
            )
        return values
