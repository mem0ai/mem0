from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChromaDbConfig(BaseModel):
    try:
        from chromadb.api.client import Client
    except ImportError:
        raise ImportError("The 'chromadb' library is required. Please install it using 'pip install chromadb'.")
    Client: ClassVar[type] = Client

    collection_name: str = Field("mem0", description="Default name for the collection/database")
    client: Optional[Client] = Field(None, description="Existing ChromaDB client instance")
    path: Optional[str] = Field(None, description="Path to the database directory")
    host: Optional[str] = Field(None, description="Database connection remote host")
    port: Optional[int] = Field(None, description="Database connection remote port")
    # ChromaDB Cloud configuration
    api_key: Optional[str] = Field(None, description="ChromaDB Cloud API key")
    tenant: Optional[str] = Field(None, description="ChromaDB Cloud tenant ID")

    @model_validator(mode="before")
    def check_connection_config(cls, values):
        host, port, path = values.get("host"), values.get("port"), values.get("path")
        api_key, tenant = values.get("api_key"), values.get("tenant")
        
        # Check if cloud configuration is provided
        cloud_config = bool(api_key and tenant)
        
        # If cloud configuration is provided, remove any default path that might have been added
        if cloud_config and path == "/tmp/chroma":
            values.pop("path", None)
            return values
        
        # Check if local/server configuration is provided (excluding default tmp path for cloud config)
        local_config = bool(path and path != "/tmp/chroma") or bool(host and port)
        
        if not cloud_config and not local_config:
            raise ValueError("Either ChromaDB Cloud configuration (api_key, tenant) or local configuration (path or host/port) must be provided.")
        
        if cloud_config and local_config:
            raise ValueError("Cannot specify both cloud configuration and local configuration. Choose one.")
            
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

    model_config = ConfigDict(arbitrary_types_allowed=True)
