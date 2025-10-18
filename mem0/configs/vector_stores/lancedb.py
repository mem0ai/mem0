from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class LanceDBConfig(BaseModel):
    """Configuration for LanceDB vector database."""

    uri: str = Field(
        "./lancedb",
        description="URI for LanceDB database (file path or connection string)"
    )
    collection_name: str = Field("memories", description="Collection/table name")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    table_name: Optional[str] = Field(
        None,
        description="Override table name (uses collection_name if not provided)"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that no extra fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields

        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )

        return values

    class Config:
        arbitrary_types_allowed = True
