from typing import Optional,ClassVar

from pydantic import BaseModel, Field, field_validator, model_validator

class QdrantConfig(BaseModel):
    from qdrant_client import QdrantClient 
    QdrantClient: ClassVar[type] = QdrantClient

    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    client: Optional[QdrantClient] = Field(None, description="Existing Qdrant client instance")
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

    class Config:
        arbitrary_types_allowed = True
