from typing import Any, ClassVar, Dict, Optional

from pydantic import BaseModel, Field, model_validator

class LanceDBConfig(BaseModel):
    table_name: str = Field("mem0", description="Name of the table")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    uri: Optional[str] = Field(None, description="Path to the database uriectory")

    @model_validator(mode="before")
    def check_host_port_or_uri(cls, values):
        uri = values.get("uri")
        if not uri:
            raise ValueError("Path to the directory 'uri' must be provided.")
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
