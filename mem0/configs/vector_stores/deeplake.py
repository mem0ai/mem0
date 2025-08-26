from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class DeepLakeConfig(BaseModel):
    try:
        import deeplake
    except ImportError:
        raise ImportError("The 'deeplake' library is required. Please install it using 'pip install deeplake'.")

    url: str = Field("mem://mem0", description="Default url for the collection")
    creds: Optional[dict] = Field(None, description="Authentication credentials")
    token: Optional[str] = Field(None, description="Authentication token")
    embedding_model_dims: Optional[int] = Field(768, description="Dimension of the embedding vector")
    quantize: Optional[bool] = Field(False, description="Whether to quantize the vectors")
    client: Optional[deeplake.Dataset] = Field(None, description="DeepLake dataset client instance")

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
