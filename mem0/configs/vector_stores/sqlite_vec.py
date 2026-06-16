from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SQLiteVecConfig(BaseModel):
    collection_name: str = Field("mem0", description="Default name for the collection")
    path: Optional[str] = Field(None, description="Path to store the SQLite database file")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    inline_payload: bool = Field(
        True,
        description="When True, store payload directly in the vec0 table (single-table, KNN filter). "
        "When False, store payload in a separate metadata table (two-table, better for large payloads).",
    )

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