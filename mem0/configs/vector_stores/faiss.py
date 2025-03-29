from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class FAISSConfig(BaseModel):
    collection_name: str = Field("mem0", description="Default name for the collection")
    path: Optional[str] = Field(None, description="Path to store FAISS index and metadata")
    distance_strategy: str = Field(
        "euclidean", description="Distance strategy to use. Options: 'euclidean', 'inner_product', 'cosine'"
    )
    normalize_L2: bool = Field(
        False, description="Whether to normalize L2 vectors (only applicable for euclidean distance)"
    )

    @model_validator(mode="before")
    @classmethod
    def validate_distance_strategy(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        distance_strategy = values.get("distance_strategy")
        if distance_strategy and distance_strategy not in ["euclidean", "inner_product", "cosine"]:
            raise ValueError("Invalid distance_strategy. Must be one of: 'euclidean', 'inner_product', 'cosine'")
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
