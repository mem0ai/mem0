from typing import Optional

from pydantic import BaseModel, Field

class ClickhouseConfig(BaseModel):
    collection_name: str = Field("mem0", description="Name of the collection (ClickHouse table)")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    host: str = Field("localhost", description="ClickHouse server host")
    port: int = Field(8123, description="ClickHouse server port (HTTP interface)")
    username: str = Field("default", description="Username for authentication")
    password: str = Field("", description="Password for authentication")
    database: str = Field("default", description="Database name")
