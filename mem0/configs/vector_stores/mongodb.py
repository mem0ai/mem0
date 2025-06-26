from typing import Any, Dict, Optional, Callable, List

from pydantic import BaseModel, Field, root_validator


class MongoDBConfig(BaseModel):
    """Configuration for MongoDB vector database."""

    db_name: str = Field("mem0_db", description="Name of the MongoDB database")
    collection_name: str = Field("mem0", description="Name of the MongoDB collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding vectors")
    user: Optional[str] = Field(None, description="MongoDB user for authentication")
    password: Optional[str] = Field(None, description="Password for the MongoDB user")
    host: Optional[str] = Field("localhost", description="MongoDB host. Default is 'localhost'")
    port: Optional[int] = Field(27017, description="MongoDB port. Default is 27017")

    @root_validator(pre=True)
    def check_auth_and_connection(cls, values):
        user = values.get("user")
        password = values.get("password")
        if (user is None) != (password is None):
            raise ValueError("Both 'user' and 'password' must be provided together or omitted together.")

        host = values.get("host")
        port = values.get("port")
        if host is None:
            raise ValueError("The 'host' must be provided.")
        if port is None:
            raise ValueError("The 'port' must be provided.")
        return values

    @root_validator(pre=True)
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = set(cls.__fields__)
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields
        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please provide only the following fields: {', '.join(allowed_fields)}."
            )
        return values
