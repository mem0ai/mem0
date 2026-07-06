from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class S3VectorsConfig(BaseModel):
    vector_bucket_name: str = Field(description="Name of the S3 Vector bucket")
    collection_name: str = Field("mem0", description="Name of the vector index")
    embedding_model_dims: int = Field(1536, description="Dimension of the embedding vector")
    distance_metric: str = Field(
        "cosine",
        description="Distance metric for similarity search. Options: 'cosine', 'euclidean'",
    )
    region_name: Optional[str] = Field(None, description="AWS region for the S3 Vectors client")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
