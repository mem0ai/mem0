from pydantic import BaseModel, ConfigDict, Field


class BaiduDBConfig(BaseModel):
    endpoint: str = Field("http://localhost:8287", description="Endpoint URL for Baidu VectorDB")
    account: str = Field("root", description="Account for Baidu VectorDB")
    api_key: str = Field(None, description="API Key for Baidu VectorDB")
    database_name: str = Field("mem0", description="Name of the database")
    table_name: str = Field("mem0", description="Name of the table")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    metric_type: str = Field("L2", description="Metric type for similarity search")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
