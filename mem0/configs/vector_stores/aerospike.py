from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class AerospikeConfig(BaseModel):
    """Configuration for the Aerospike Vector Search vector store."""

    host: str = Field("localhost", description="Aerospike Vector Search service host")
    port: int = Field(5000, description="Aerospike Vector Search service port")
    namespace: str = Field("mem0", description="Aerospike namespace to store vectors in")
    set_name: str = Field("memories", description="Aerospike set (table) name within the namespace")
    index_name: str = Field("mem0_index", description="Name of the HNSW vector index")
    vector_field: str = Field("embedding", description="Bin name that holds the vector data")
    embedding_model_dims: int = Field(1536, description="Dimensionality of the embedding vectors")
    distance_metric: str = Field(
        "COSINE",
        description=(
            "Distance metric for the vector index. "
            "Supported values: 'COSINE', 'SQUARED_EUCLIDEAN', 'DOT_PRODUCT'"
        ),
    )
    username: Optional[str] = Field(None, description="Username for Aerospike authentication (optional)")
    password: Optional[str] = Field(None, description="Password for Aerospike authentication (optional)")
    use_tls: bool = Field(False, description="Whether to use TLS for the AVS connection")
    tls_cafile: Optional[str] = Field(None, description="Path to CA certificate file for TLS verification")

    model_config = ConfigDict(arbitrary_types_allowed=True)

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        allowed_fields = {
            "host",
            "port",
            "namespace",
            "set_name",
            "index_name",
            "vector_field",
            "embedding_model_dims",
            "distance_metric",
            "username",
            "password",
            "use_tls",
            "tls_cafile",
        }
        extra = set(values.keys()) - allowed_fields
        if extra:
            raise ValueError(
                f"Extra fields not allowed: {', '.join(sorted(extra))}. "
                f"Allowed fields: {', '.join(sorted(allowed_fields))}"
            )
        return values
