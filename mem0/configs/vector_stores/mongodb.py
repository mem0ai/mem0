from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, model_validator


class MongoDBConfig(BaseModel):
    """Configuration for MongoDB vector database."""

    db_name: str = Field("mem0_db", description="Name of the MongoDB database")
    collection_name: str = Field("mem0", description="Name of the MongoDB collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding model")
    mongo_uri: Optional[str] = Field(None, description="MongoDB connection URI (recommended)")
    user: Optional[str] = Field(None, description="MongoDB user for authentication")
    password: Optional[str] = Field(None, description="Password for the MongoDB user")
    host: Optional[str] = Field("localhost", description="MongoDB host")
    port: Optional[int] = Field(27017, description="MongoDB port")

    @model_validator(mode="before")
    @classmethod
    def validate_connection_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connection configuration and build mongo_uri if needed."""
        mongo_uri = values.get("mongo_uri")
        user = values.get("user")
        password = values.get("password")
        host = values.get("host", "localhost")
        port = values.get("port", 27017)

        # If mongo_uri is provided, use it directly (Method 1)
        if mongo_uri:
            return values

        # Otherwise, validate and build from individual credentials (Method 2)
        if (user is None) != (password is None):
            raise ValueError("Both 'user' and 'password' must be provided together or omitted together.")

        # Build mongo_uri from individual components
        if user and password:
            values["mongo_uri"] = f"mongodb://{user}:{password}@{host}:{port}"
        else:
            values["mongo_uri"] = f"mongodb://{host}:{port}"

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

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override model_dump to return only the fields needed by MongoVector constructor."""
        data = super().model_dump(**kwargs)
        # Return only the fields that MongoVector.__init__ expects
        return {
            "db_name": data["db_name"],
            "collection_name": data["collection_name"],
            "embedding_model_dims": data["embedding_model_dims"],
            "mongo_uri": data["mongo_uri"]
        }
