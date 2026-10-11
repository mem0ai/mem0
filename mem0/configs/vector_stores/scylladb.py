from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ScyllaDBConfig(BaseModel):
    """Configuration for ScyllaDB vector database (ScyllaDB Cloud with vector search)."""

    contact_points: List[str] = Field(
        ...,
        description="List of contact point addresses (e.g., ['node-0.aws-us-east-1.x.clusters.scylla.cloud'])",
    )
    port: int = Field(9042, description="ScyllaDB CQL port")
    username: Optional[str] = Field(None, description="Database username")
    password: Optional[str] = Field(None, description="Database password")
    keyspace: str = Field("mem0", description="Keyspace name")
    collection_name: str = Field("memories", description="Table name")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    distance: str = Field(
        "cosine",
        description="Distance metric for the vector index: 'cosine', 'dot_product', or 'euclidean'",
    )
    datacenter: Optional[str] = Field(
        None,
        description="Local datacenter name for DC-aware routing (recommended for ScyllaDB Cloud)",
    )
    use_ssl: bool = Field(False, description="Enable SSL/TLS (required by ScyllaDB Cloud)")
    ssl_cert_path: Optional[str] = Field(
        None,
        description="Path to a CA certificate file for SSL verification (defaults to system CA bundle)",
    )
    replication_strategy: str = Field("NetworkTopologyStrategy", description="Keyspace replication strategy")
    replication_factor: int = Field(3, description="Keyspace replication factor")

    @model_validator(mode="before")
    @classmethod
    def check_auth(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate authentication parameters."""
        username = values.get("username")
        password = values.get("password")

        # Both username and password must be provided together or not at all
        if (username and not password) or (password and not username):
            raise ValueError("Both 'username' and 'password' must be provided together for authentication")

        return values

    @model_validator(mode="before")
    @classmethod
    def check_distance(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the distance metric."""
        distance = values.get("distance", "cosine")
        if distance not in ("cosine", "dot_product", "euclidean"):
            raise ValueError(
                f"Unsupported distance metric '{distance}'. Supported: 'cosine', 'dot_product', 'euclidean'"
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

    model_config = ConfigDict(arbitrary_types_allowed=True)
