from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class AzureAISearchConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection")
    service_name: str = Field(None, description="Azure AI Search service name")
    api_key: str = Field(None, description="API key for the Azure AI Search service")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    compression_type: Optional[str] = Field(
        None, description="Type of vector compression to use. Options: 'scalar', 'binary', or None"
    )
    use_float16: bool = Field(
        False,
        description="Whether to store vectors in half precision (Edm.Half) instead of full precision (Edm.Single)",
    )
    hybrid_search: bool = Field(
        False, description="Whether to use hybrid search. If True, vector_filter_mode must be 'preFilter'"
    )
    vector_filter_mode: Optional[str] = Field(
        "preFilter", description="Mode for vector filtering. Options: 'preFilter', 'postFilter'"
    )

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
