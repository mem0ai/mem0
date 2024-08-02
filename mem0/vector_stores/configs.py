from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


def create_default_config(provider: str):
    """Create a default configuration based on the provider."""
    if provider == "qdrant":
        return QdrantConfig(path="/tmp/qdrant")
    elif provider == "chromadb":
        return ChromaDbConfig(path="/tmp/chromadb")
    else:
        raise ValueError(f"Unsupported vector store provider: {provider}")


class QdrantConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    client: Optional[str] = Field(None, description="Existing Qdrant client instance")
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field("/tmp/qdrant", description="Path for local Qdrant database")
    url: Optional[str] = Field(None, description="Full URL for Qdrant server")
    api_key: Optional[str] = Field(None, description="API key for Qdrant server")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        host, port, path, url, api_key = (
            values.get("host"),
            values.get("port"),
            values.get("path"),
            values.get("url"),
            values.get("api_key"),
        )
        if not path and not (host and port) and not (url and api_key):
            raise ValueError(
                "Either 'host' and 'port' or 'url' and 'api_key' or 'path' must be provided."
            )
        return values


class ChromaDbConfig(BaseModel):
    collection_name: str = Field("mem0", description="Default name for the collection")
    client: Optional[str] = Field(None, description="Existing ChromaDB client instance")
    path: Optional[str] = Field(None, description="Path to the database directory")
    host: Optional[str] = Field(None, description="Database connection remote host")
    port: Optional[str] = Field(None, description="Database connection remote port")

    @model_validator(mode="before")
    def check_host_port_or_path(cls, values):
        host, port, path = values.get("host"), values.get("port"), values.get("path")
        if not path and not (host and port):
            raise ValueError("Either 'host' and 'port' or 'path' must be provided.")
        return values


class VectorStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the vector store (e.g., 'qdrant', 'chromadb', 'elasticsearch')",
        default="qdrant",
    )
    config: Optional[dict] = Field(
        description="Configuration for the specific vector store",
        default=None
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        
        if v is None:
            return create_default_config(provider)
        
        if isinstance(v, dict):
            if provider == "qdrant":
                return QdrantConfig(**v)
            elif provider == "chromadb":
                return ChromaDbConfig(**v)
        
        return v

    @model_validator(mode="after")
    def ensure_config_type(cls, values):
        provider = values.provider
        config = values.config
        
        if config is None:
            values.config = create_default_config(provider)
        elif isinstance(config, dict):
            if provider == "qdrant":
                values.config = QdrantConfig(**config)
            elif provider == "chromadb":
                values.config = ChromaDbConfig(**config)
        elif not isinstance(config, (QdrantConfig, ChromaDbConfig)):
            raise ValueError(f"Invalid config type for provider {provider}")
        
        return values