from pydantic import BaseModel, ConfigDict, Field


class ValkeyConfig(BaseModel):
    """Configuration for Valkey vector store."""

    valkey_url: str = Field(..., description="Valkey server URL (e.g., redis://localhost:6379)")
    collection_name: str = Field(..., description="Name of the index / collection")
    embedding_model_dims: int = Field(..., description="Dimensions of the embedding model")
    timezone: str = Field("UTC", description="Timezone for timestamp handling")
    index_type: str = Field("hnsw", description="Index type: 'hnsw' (default) or 'flat'")
    hnsw_m: int = Field(16, description="HNSW: number of connections per layer")
    hnsw_ef_construction: int = Field(200, description="HNSW: search width during index construction")
    hnsw_ef_runtime: int = Field(10, description="HNSW: search width during queries")
    cluster_mode: bool = Field(False, description="Enable cluster mode for Valkey cluster (CME) deployments")

    model_config = ConfigDict(arbitrary_types_allowed=False, extra="forbid")
