from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class VSAGConfig(BaseModel):
    """Configuration for VSAG vector store."""

    collection_name: str = Field("mem0", description="Name of the collection")
    path: Optional[str] = Field(None, description="Path to store VSAG index and metadata")
    dim: int = Field(1536, description="Dimension of the embedding vector")
    index_type: str = Field(
        "hnsw",
        description="Type of VSAG index (e.g., 'hnsw', 'hgraph', 'diskann', 'ivf')"
    )
    metric_type: str = Field(
        "l2",
        description="Distance metric type (e.g., 'l2', 'ip', 'cosine')"
    )
    dtype: str = Field(
        "float32",
        description="Data type for vectors (e.g., 'float32', 'int8')"
    )
    # Index-specific parameters
    index_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional index parameters as dict"
    )
    search_params: Optional[Dict[str, Any]] = Field(
        None,
        description="Default search parameters as dict"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True)