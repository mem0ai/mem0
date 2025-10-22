from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


class CassandraConfig(BaseModel):
    """Configuration for Apache Cassandra vector database."""

    contact_points: List[str] = Field(
        ...,
        description="List of contact point addresses (e.g., ['127.0.0.1', '127.0.0.2'])"
    )
    port: int = Field(9042, description="Cassandra port")
    username: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password")
    keyspace: str = Field("mem0", description="Keyspace name")
    collection_name: str = Field("memories", description="Table name")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    secure_connect_bundle: Optional[str] = Field(
        None,
        description="Path to secure connect bundle for DataStax Astra DB"
    )
    protocol_version: int = Field(4, description="CQL protocol version")
    load_balancing_policy: Optional[Any] = Field(
        None,
        description="Custom load balancing policy object"
    )

    @model_validator(mode="before")
    @classmethod
    def check_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authentication parameters."""
        username = values.get("username")
        password = values.get("password")

        # Both username and password must be provided together or not at all
        if (username and not password) or (password and not username):
            raise ValueError(
                "Both 'username' and 'password' must be provided together for authentication"
            )

        return values

    @model_validator(mode="before")
    @classmethod
    def check_connection_config(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate connection configuration."""
        secure_connect_bundle = values.get("secure_connect_bundle")
        contact_points = values.get("contact_points")

        # Either secure_connect_bundle or contact_points must be provided
        if not secure_connect_bundle and not contact_points:
            raise ValueError(
                "Either 'contact_points' or 'secure_connect_bundle' must be provided"
            )

        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate that no extra fields are provided."""
        allowed_fields = set(cls.model_fields.keys())
        input_fields = set(values.keys())
        extra_fields = input_fields - allowed_fields

        if extra_fields:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(extra_fields)}. "
                f"Please input only the following fields: {', '.join(allowed_fields)}"
            )

        return values

    class Config:
        arbitrary_types_allowed = True

