from pydantic import BaseModel, Field


class TairConfig(BaseModel):
    host: str = Field("localhost", description="Tair host address")
    port: int = Field(6379, description="Tair port number")
    db: str = Field("mem0", description="Tair db name")
    username: str = Field(None, description="Tair username")
    password: str = Field(None, description="Tair password")
    embedding_model_dims: int = Field(1024, description="Embedding model dimensions")

    model_config = {
        "arbitrary_types_allowed": True,
    }
