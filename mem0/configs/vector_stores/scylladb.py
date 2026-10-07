from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScyllaDBConfig(BaseModel):
    """Configuration for the ScyllaDB vector store."""

    contact_points: List[str] = Field(
        ...,
        description="List of ScyllaDB node addresses (e.g., ['node1.example.com'])",
    )
    port: int = Field(9042, description="CQL native-transport port")
    username: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password")
    keyspace: str = Field("mem0", description="Keyspace name")
    collection_name: str = Field("memories", description="Table name")
    embedding_model_dims: int = Field(
        1536, description="Dimensions of the embedding model vectors"
    )
    datacenter: Optional[str] = Field(
        None,
        description=(
            "Local datacenter name for DC-aware load balancing. "
            "Required when connecting to ScyllaDB Cloud (e.g., 'AWS_US_EAST_1')."
        ),
    )
    use_ssl: bool = Field(
        False,
        description="Enable SSL/TLS.",
    )
    ssl_cert_path: Optional[str] = Field(
        None,
        description=(
            "Path to a CA certificate file for SSL verification. "
            "Leave as None to use the system's default CA bundle."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def check_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        username = values.get("username")
        password = values.get("password")
        if bool(username) != bool(password):
            raise ValueError(
                "Both 'username' and 'password' must be provided together for authentication."
            )
        return values

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed = set(cls.model_fields.keys())
        extra = set(values.keys()) - allowed
        if extra:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(sorted(extra))}. "
                f"Allowed fields: {', '.join(sorted(allowed))}"
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
