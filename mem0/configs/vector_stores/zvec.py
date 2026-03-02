from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ZvecConfig(BaseModel):
    """Configuration for the Zvec vector store backend."""

    try:
        from zvec import Collection as ZvecCollection
    except ImportError:
        raise ImportError("The 'zvec' library is required. Please install it using 'pip install zvec'.")

    ZvecCollection: ClassVar[type] = ZvecCollection

    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    path: Optional[str] = Field("/tmp/zvec", description="Path for local Zvec collection storage")
    client: Optional[ZvecCollection] = Field(None, description="Existing Zvec collection instance")

    read_only: Optional[bool] = Field(False, description="Open the Zvec collection in read-only mode")
    enable_mmap: Optional[bool] = Field(True, description="Enable memory-mapped I/O for collection data")

    @model_validator(mode="before")
    @classmethod
    def check_client_or_path(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        client = values.get("client")
        path = values.get("path")

        if isinstance(path, str):
            values["path"] = path.strip()

        if client is None and (path is None or (isinstance(path, str) and not path.strip())):
            raise ValueError("Either 'client' or a non-empty 'path' must be provided.")

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
