from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class OpenSearchConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the index")
    host: str = Field("localhost", description="OpenSearch host")
    port: int = Field(9200, description="OpenSearch port")
    user: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    api_key: Optional[str] = Field(None, description="API key for authentication (if applicable)")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    verify_certs: bool = Field(False, description="Verify SSL certificates (default False for OpenSearch)")
    use_ssl: bool = Field(False, description="Use SSL for connection (default False for OpenSearch)")
    auto_create_index: bool = Field(True, description="Automatically create index during initialization")
    http_auth: Optional[object] = Field(None, description="HTTP authentication method / AWS SigV4")
    engine: str = Field("nmslib", description="Engine type: 'nmslib', 'faiss', or 'lucene' (AOSS only supports nmslib or faiss)")

    @model_validator(mode="before")
    @classmethod
    def validate_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Check if host is provided
        if not values.get("host"):
            raise ValueError("Host must be provided for OpenSearch")

        # Authentication: Either API key or user/password must be provided
        if not any([values.get("api_key"), (values.get("user") and values.get("password")), values.get("http_auth")]):
            raise ValueError("Either api_key or user/password must be provided for OpenSearch authentication")

        # Validate engine for AOSS if http_auth is set with service=aoss
        http_auth = values.get("http_auth")
        if http_auth and hasattr(http_auth, "service") and http_auth.service == "aoss":
            engine = values.get("engine", "nmslib")
            if engine not in ["nmslib", "faiss"]:
                raise ValueError("Amazon OpenSearch Service Serverless only supports 'nmslib' or 'faiss' engines")

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. " f"Allowed fields: {', '.join(allowed_fields)}"
            )
        return values
