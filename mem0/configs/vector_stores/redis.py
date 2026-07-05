from pydantic import BaseModel, ConfigDict, Field


# TODO: Upgrade to latest pydantic version
class RedisDBConfig(BaseModel):
    redis_url: str = Field(..., description="Redis URL")
    collection_name: str = Field("mem0", description="Collection name")
    embedding_model_dims: int = Field(1536, description="Embedding model dimensions")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
