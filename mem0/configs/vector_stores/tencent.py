from typing import Any, Dict, List

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TencentVectorDBConfig(BaseModel):
    url: str = Field(None, description="URL for TencentVectorDB instance")
    key: str = Field(None, description="API key for TencentVectorDB instance")
    username: str = Field("root", description="Username for TencentVectorDB instance")
    database_name: str = Field("mem0", description="Name of the database")
    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    metric_type: str = Field("COSINE", description="Metric type for similarity search")
    index_type: str = Field("HNSW", description="Index type for vectors")
    shard_num: int = Field(2, description="Number of shards in the collection")
    replica_num: int = Field(2, description="Number of replicas for the collection")
    field_type: str = Field("vector", description="Field type for the embedding vectors")
    params: Dict[str, Any] = Field({}, description="Parameters for the index")
    no_index_fields: List[str] = Field([], description="Fields that will not be indexed")

    @model_validator(mode="before")
    @classmethod
    def validate_extra_fields(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        url, key = values.get("url"), values.get("key")
        if not url or not key:
            raise ValueError(
                "Both 'url' and 'key' must be provided."
            )
        return values

    model_config = ConfigDict(arbitrary_types_allowed=True)
