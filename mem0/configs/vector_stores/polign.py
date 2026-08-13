from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PolignConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    url: str = Field("http://localhost:23000", description="Base URL of the polign server's HTTP listener")
    api_key: Optional[str] = Field(
        None,
        description="API key ('plgn_<key_id>_<secret>'). Optional — servers started without -auth-stores need none. "
        "Falls back to the POLIGN_API_KEY environment variable.",
    )
    ef: int = Field(0, description="HNSW beam width override for searches (0 = server default)")
    batch_size: int = Field(1000, description="Vectors per put_many request (server max 5000)")

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
