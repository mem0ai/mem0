from collections.abc import Callable
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class ElasticsearchConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the index")
    host: str = Field("localhost", description="Elasticsearch host")
    port: int = Field(9200, description="Elasticsearch port")
    user: Optional[str] = Field(None, description="Username for authentication")
    password: Optional[str] = Field(None, description="Password for authentication")
    cloud_id: Optional[str] = Field(None, description="Cloud ID for Elastic Cloud")
    api_key: Optional[str] = Field(None, description="API key for authentication")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    verify_certs: bool = Field(True, description="Verify SSL certificates")
    use_ssl: bool = Field(True, description="Use SSL for connection")
    auto_create_index: bool = Field(True, description="Automatically create index during initialization")
    custom_search_query: Optional[Callable[[List[float], int, Optional[Dict]], Dict]] = Field(
        None, description="Custom search query function. Parameters: (query, limit, filters) -> Dict"
    )
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers to include in requests")

    @model_validator(mode="before")
    @classmethod
    def validate_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        # Check if either cloud_id or host/port is provided
        if not values.get("cloud_id") and not values.get("host"):
            raise ValueError("Either cloud_id or host must be provided")

        # Check if authentication is provided
        if not any([values.get("api_key"), (values.get("user") and values.get("password"))]):
            raise ValueError("Either api_key or user/password must be provided")

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_headers(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate headers format and content"""
        headers = values.get("headers")
        if headers is not None:
            # Check if headers is a dictionary
            if not isinstance(headers, dict):
                raise ValueError("headers must be a dictionary")
            
            # Check if all keys and values are strings
            for key, value in headers.items():
                if not isinstance(key, str) or not isinstance(value, str):
                    raise ValueError("All header keys and values must be strings")
        
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values
