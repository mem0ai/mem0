from pydantic import BaseModel, Field
from typing import Optional

class LanceDBConfig(BaseModel):
    uri: str = Field(..., description="LanceDB URI (e.g. local path or s3://bucket/path)") 
    table_name: str = Field("vectorstore", description="Table name to store embeddings")
    id_key: str = Field("id", description="Column name for unique IDs")
    vector_key: str = Field("vector", description="Column name for embeddings")
    distance_metric: str = Field("cosine", description="Distance metric: 'L2', 'cosine', or 'dot'")
    embedding_model_dims: Optional[int]
