from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class MongoDBConfig(BaseModel):
    """Configuration for MongoDB vector database."""

    db_name: str = Field("mem0_db", description="Name of the MongoDB database")
    collection_name: str = Field("mem0", description="Name of the MongoDB collection")
    embedding_model_dims: Optional[int] = Field(1536, description="Dimensions of the embedding vectors")
    mongo_uri: str = Field("mongodb://localhost:27017", description="MongoDB URI. Default is mongodb://localhost:27017")

    model_config = ConfigDict(arbitrary_types_allowed=False, extra="forbid")
