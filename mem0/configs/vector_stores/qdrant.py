from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class QdrantConfig(BaseModel):
    from qdrant_client import QdrantClient

    QdrantClient: ClassVar[type] = QdrantClient

    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    client: Optional[QdrantClient] = Field(None, description="Existing Qdrant client instance")
    host: Optional[str] = Field(None, description="Host address for Qdrant server")
    port: Optional[int] = Field(None, description="Port for Qdrant server")
    path: Optional[str] = Field(None, description="Path for local Qdrant database")
    url: Optional[str] = Field(None, description="Full URL for Qdrant server")
    api_key: Optional[str] = Field(None, description="API key for Qdrant server")
    https: Optional[bool] = Field(
        None,
        description="Whether to force HTTPS on or off. Explicit schemes in url take precedence.",
    )
    on_disk: Optional[bool] = Field(
        False,
        description=(
            "Enables persistent storage. Vectors are kept on disk (True) or in memory (False). "
            "Does not delete the local database path."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def check_host_port_or_path(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(values, dict):
            return values
        if values.get("client") is not None:
            return values

        host, port, path, url = (
            values.get("host"),
            values.get("port"),
            values.get("path"),
            values.get("url"),
        )
        has_host = isinstance(host, str) and bool(host.strip())
        has_path = isinstance(path, str) and bool(path.strip())
        has_url = isinstance(url, str) and bool(url.strip())
        if has_host:
            if isinstance(port, str) and port.isdigit():
                port = int(port)
                values["port"] = port
            if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
                raise ValueError("Qdrant host mode requires a port between 1 and 65535.")
        elif port is not None:
            raise ValueError("Qdrant port requires a non-empty host.")

        if not has_path and not has_host and not has_url:
            raise ValueError("Either 'host' and 'port', 'url', or 'path' must be provided.")
        if has_url and has_host:
            raise ValueError("'url' and 'host'/'port' modes cannot be configured together.")
        if has_path and (has_url or has_host):
            raise ValueError("Local 'path' and remote Qdrant endpoint modes cannot be configured together.")
        if has_path:
            remote_only = [key for key in ("api_key", "https") if values.get(key) is not None]
            if remote_only:
                raise ValueError(
                    "Local 'path' mode cannot use remote-only option(s): " + ", ".join(sorted(remote_only)) + "."
                )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(values, dict):
            return values
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. Please input only the following fields: {', '.join(allowed_fields)}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
