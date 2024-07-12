from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator


class QdrantConfig(BaseModel):
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field(None, description="Path for local Qdrant database")
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


class VectorStoreConfig(BaseModel):
    provider: str = Field(
        description="Provider of the vector store (e.g., 'qdrant', 'chromadb', 'elasticsearch')",
        default="qdrant",
    )
    config: QdrantConfig = Field(
        description="Configuration for the specific vector store",
        default=QdrantConfig(path="/tmp/qdrant"),
    )

    @field_validator("config")
    def validate_config(cls, v, values):
        provider = values.data.get("provider")
        if provider == "qdrant":
            return QdrantConfig(**v.model_dump())
        else:
            raise ValueError(f"Unsupported vector store provider: {provider}")
