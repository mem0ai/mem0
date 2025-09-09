from pydantic import BaseModel


class ValkeyConfig(BaseModel):
    """Configuration for Valkey vector store."""

    valkey_url: str
    collection_name: str
    embedding_model_dims: int
    timezone: str = "UTC"
    index_type: str = "hnsw"  # Default to HNSW, can be 'hnsw' or 'flat'
    # HNSW specific parameters with recommended defaults
    hnsw_m: int = 16  # Number of connections per layer (default from Valkey docs)
    hnsw_ef_construction: int = 200  # Search width during construction
    hnsw_ef_runtime: int = 10  # Search width during queries
