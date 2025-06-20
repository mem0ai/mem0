from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class MongoDBConfig(BaseModel):
    """Configuration for MongoDB vector database."""

    db_name: str = Field("mem0_db", description="Name of the MongoDB database")
    collection_name: str = Field("mem0", description="Name of the MongoDB collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    mongo_uri: str = Field(..., description="MongoDB connection URI")

    @model_validator(mode="before")
    @classmethod
    def validate_mongo_uri(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that mongo_uri is provided."""
        mongo_uri = values.get("mongo_uri")

        if not mongo_uri:
            raise ValueError("mongo_uri is required. Please provide a MongoDB connection string.")

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that only allowed fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please provide only the following fields: {', '.join(allowed_fields)}."
            )
        return values
