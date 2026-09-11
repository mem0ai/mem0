from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class LanceDBConfig(BaseModel):
    collection_name: str = Field("mem0", description="Default name for the table")
    path: Optional[str] = Field("/tmp/lancedb", description="Path to the LanceDB database directory")
    embedding_model_dims: int = Field(1536, gt=0, description="Dimension of the embedding vector")
    distance: str = Field("cosine", description="Distance metric. Options: 'cosine', 'l2', 'dot'")

    @model_validator(mode="before")
    @classmethod
    def validate_distance(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        distance = values.get("distance")
        if distance and distance not in {"cosine", "l2", "dot"}:
            raise ValueError("Invalid distance. Must be one of: 'cosine', 'l2', 'dot'")
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

    model_config = ConfigDict(arbitrary_types_allowed=True)
