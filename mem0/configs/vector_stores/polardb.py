from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

SUPPORTED_INDEX_TYPES = ("FAISS_HNSW_FLAT", "FAISS_HNSW_PQ", "FAISS_HNSW_SQ")


class PolarDBConfig(BaseModel):
    """Configuration for PolarDB MySQL vector database."""

    host: str = Field(..., description="PolarDB MySQL server host")
    port: int = Field(3306, description="PolarDB MySQL server port")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    database: str = Field(..., description="Database name")
    collection_name: str = Field("mem0", description="Collection/table name")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    metric: str = Field(
        "cosine",
        description="Distance metric for vector index (cosine, euclidean, inner_product)",
    )
    index_type: str = Field(
        "FAISS_HNSW_FLAT",
        description="Vector index algorithm (FAISS_HNSW_FLAT, FAISS_HNSW_PQ, FAISS_HNSW_SQ)",
    )
    hnsw_m: int = Field(16, description="HNSW max_degree parameter (number of connections per node)")
    hnsw_ef_construction: int = Field(200, description="HNSW ef_construction parameter")
    pq_m: Optional[int] = Field(
        None,
        description="Product Quantization subspace count (required when index_type is FAISS_HNSW_PQ, must divide embedding_model_dims)",
    )
    pq_nbits: Optional[int] = Field(
        None,
        description="Product Quantization bits per subspace (required when index_type is FAISS_HNSW_PQ, max 24)",
    )
    sq_type: Optional[str] = Field(
        None,
        description="Scalar Quantization type (required when index_type is FAISS_HNSW_SQ)",
    )
    ssl_ca: Optional[str] = Field(None, description="Path to SSL CA certificate")
    ssl_disabled: bool = Field(False, description="Disable SSL connection")
    minconn: int = Field(1, description="Minimum number of connections in the pool")
    maxconn: int = Field(5, description="Maximum number of connections in the pool")
    connection_pool: Optional[Any] = Field(
        None,
        description="Pre-configured connection pool object (overrides other connection parameters)",
    )

    @model_validator(mode="before")
    @classmethod
    def check_required_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate required fields when no pre-configured pool is provided."""
        if values.get("connection_pool") is not None:
            return values

        required_fields = ["host", "user", "password", "database"]
        missing_fields = [field for field in required_fields if not values.get(field)]

        if missing_fields:
            raise ValueError(
                f"Missing required fields: {', '.join(missing_fields)}. "
                f"These fields are required when not using a pre-configured connection_pool."
            )

        return values

    @model_validator(mode="before")
    @classmethod
    def check_metric(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate metric value."""
        metric = values.get("metric", "cosine")
        allowed = ("cosine", "euclidean", "inner_product")
        if metric not in allowed:
            raise ValueError(f"Invalid metric '{metric}'. Must be one of: {', '.join(allowed)}")
        return values

    @model_validator(mode="before")
    @classmethod
    def check_index_type_and_params(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Validate index_type and its associated parameters."""
        index_type = values.get("index_type", "FAISS_HNSW_FLAT")
        if index_type not in SUPPORTED_INDEX_TYPES:
            raise ValueError(
                f"Invalid index_type '{index_type}'. Must be one of: {', '.join(SUPPORTED_INDEX_TYPES)}"
            )

        if index_type == "FAISS_HNSW_PQ":
            if values.get("pq_m") is None:
                raise ValueError("'pq_m' is required when index_type is FAISS_HNSW_PQ")
            if values.get("pq_nbits") is None:
                raise ValueError("'pq_nbits' is required when index_type is FAISS_HNSW_PQ")

        if index_type == "FAISS_HNSW_SQ":
            if values.get("sq_type") is None:
                raise ValueError("'sq_type' is required when index_type is FAISS_HNSW_SQ")

        return values

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
