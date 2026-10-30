from pydantic import BaseModel, ConfigDict, Field


class RedisDBConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    redis_url: str = Field(..., description="Redis URL")
    collection_name: str = Field("mem0", description="Collection name")
    embedding_model_dims: int = Field(1536, description="Embedding model dimensions")
