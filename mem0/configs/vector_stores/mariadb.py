from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class MariaDBConfig(BaseModel):
    dbname: str = Field("mem0", description="Default name for the database")
    collection_name: str = Field("mem0", description="Default name for the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    user: Optional[str] = Field(None, description="Database user")
    password: Optional[str] = Field(None, description="Database password")
    host: Optional[str] = Field(None, description="Database host. Default is localhost")
    port: Optional[int] = Field(None, description="Database port. Default is 3306")
    distance_function: Optional[str] = Field("euclidean", description="Distance function for vector index ('euclidean' or 'cosine')")
    m_value: Optional[int] = Field(16, description="M parameter for HNSW index (3-200). Higher values = more accurate but slower")
    # SSL and connection options
    ssl_disabled: Optional[bool] = Field(False, description="Disable SSL connection")
    ssl_ca: Optional[str] = Field(None, description="SSL CA certificate file path")
    ssl_cert: Optional[str] = Field(None, description="SSL certificate file path")
    ssl_key: Optional[str] = Field(None, description="SSL key file path")
    connection_string: Optional[str] = Field(None, description="MariaDB connection string (overrides individual connection parameters)")
    charset: Optional[str] = Field("utf8mb4", description="Character set for the connection")
    autocommit: Optional[bool] = Field(True, description="Enable autocommit mode")

    @model_validator(mode="before")
    def check_auth_and_connection(cls, values):
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
    def validate_distance_function(cls, values):
        distance_function = values.get("distance_function", "euclidean")
        if distance_function not in ["euclidean", "cosine"]:
            raise ValueError("distance_function must be either 'euclidean' or 'cosine'")
        return values

    @model_validator(mode="before")
    def validate_m_value(cls, values):
        m_value = values.get("m_value", 16)
        if not (3 <= m_value <= 200):
            raise ValueError("m_value must be between 3 and 200")
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
