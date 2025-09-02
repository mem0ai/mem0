from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class PGVectorConfig(BaseModel):
    dbname: str = Field("postgres", description="Default name for the database")
    collection_name: str = Field("mem0", description="Default name for the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field(None, description="Database host. Default is localhost")
    port: Optional[int] = Field(None, description="Database port. Default is 1536")
    diskann: Optional[bool] = Field(False, description="Use diskann for approximate nearest neighbors search")
    hnsw: Optional[bool] = Field(True, description="Use hnsw for faster search")
    minconn: Optional[int] = Field(1, description="Minimum number of connections in the pool")
    maxconn: Optional[int] = Field(5, description="Maximum number of connections in the pool")
    # New SSL and connection options
    sslmode: Optional[str] = Field(None, description="SSL mode for PostgreSQL connection (e.g., 'require', 'prefer', 'disable')")
    connection_string: Optional[str] = Field(None, description="PostgreSQL connection string (overrides individual connection parameters)")
    connection_pool: Optional[Any] = Field(None, description="psycopg connection pool object (overrides connection string and individual parameters)")

    @model_validator(mode="before")
    def check_auth_and_connection(cls, values):
        # If connection_pool is provided, skip validation of individual connection parameters
        if values.get("connection_pool") is not None:
            return values

        # If connection_string is provided, skip validation of individual connection parameters
        if values.get("connection_string") is not None:
            return values
        
        # Otherwise, validate individual connection parameters
        user, password = values.get("user"), values.get("password")
        host, port = values.get("host"), values.get("port")
        if not user and not password:
            raise ValueError("Both 'user' and 'password' must be provided when not using connection_string.")
        if not host and not port:
            raise ValueError("Both 'host' and 'port' must be provided when not using connection_string.")
        return values

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
