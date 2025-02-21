from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class CouchbaseConfig(BaseModel):
    
    connection_str: str = Field(..., description="Connection string for Couchbase server")
    username: str = Field(..., description="Username for Couchbase authentication")
    password: str = Field(..., description="Password for Couchbase authentication")
    bucket_name: str = Field(..., description="Name of the Couchbase bucket")
    scope_name: Optional[str] = Field("_default", description="Name of the scope")
    collection_name: Optional[str] = Field("_default", description="Name of the collection")
    index_name: Optional[str] = Field(None, description="Name of the search index")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")

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

