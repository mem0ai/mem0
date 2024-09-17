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
    diskann: Optional[bool] = Field(True, description="Use diskann for approximate nearest neighbors search")

    @model_validator(mode="before")
    def check_auth_and_connection(cls, values):
        user, password = values.get("user"), values.get("password")
        host, port = values.get("host"), values.get("port")
        if not user and not password:
            raise ValueError("Both 'user' and 'password' must be provided.")
        if not host and not port:
            raise ValueError("Both 'host' and 'port' must be provided.")
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
