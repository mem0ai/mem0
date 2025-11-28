from typing import Any, Dict

from pydantic import BaseModel, Field, model_validator


class TiDBConfig(BaseModel):
    """Configuration for TiDB Vector database."""

    host: str = Field(
        "localhost",
        description="TiDB server host"
    )
    port: int = Field(4000, description="TiDB server port")
    user: str = Field("root", description="Database username")
    password: str = Field("", description="Database password")
    database: str = Field("mem0", description="Database name")
    collection_name: str = Field("memories", description="Table name for storing vectors")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")

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
