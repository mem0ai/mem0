from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class LanceDBConfig(BaseModel):
    """
    Configuration for LanceDB vector store integration.

    Attributes:
        collection_name (str): Name of the table (collection) to use or create.
        embedding_model_dims (Optional[int]): Dimensions of the embedding model. Defaults to 1536.
        uri (Optional[str]): Path or URI to the database directory or LanceDB Enterprise endpoint.
        api_key (Optional[str]): API key for LanceDB Enterprise (if required).
        region (Optional[str]): Cloud region for LanceDB Enterprise (if required).
    """

    collection_name: str = Field("mem0", description="Name of the table (collection)")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    uri: Optional[str] = Field(
        "./lancedb", description="Path or URI to the database directory or LanceDB Enterprise endpoint"
    )
    api_key: Optional[str] = Field(None, description="API key for LanceDB Enterprise (if required)")
    region: Optional[str] = Field(None, description="Cloud region for LanceDB Enterprise (if required)")

    @model_validator(mode="before")
    def check_uri_optional(cls, values):
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

    model_config = {
        "arbitrary_types_allowed": True,
    }
