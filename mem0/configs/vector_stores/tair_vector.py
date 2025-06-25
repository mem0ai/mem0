from typing import Dict, Any

from pydantic import BaseModel, Field, model_validator


class TairVectorConfig(BaseModel):
    host: str = Field("localhost", description="Tair host address")
    port: int = Field(6379, description="Tair port number")
    db: str = Field("0", description="Tair db name")
    username: str = Field(None, description="Tair username")
    password: str = Field(None, description="Tair password")
    collection_name: str = Field("mem0", description="The default collection name. When put data into TairVector and no"
                                                     "user_id provided, the data will be stored in the default "
                                                     "collection")
    embedding_model_dims: int = Field(1024, description="Embedding model dimensions")
    distance_method: str = Field("COSINE", description="Distance method, using L2/IP/JACCARD/COSINE")

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
