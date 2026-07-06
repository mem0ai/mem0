from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class MetricType(str, Enum):
    """
    Metric Constant for milvus/ zilliz server.
    """

    def __str__(self) -> str:
        return str(self.value)

    L2 = "L2"
    IP = "IP"
    COSINE = "COSINE"
    HAMMING = "HAMMING"
    JACCARD = "JACCARD"


class MilvusDBConfig(BaseModel):
    url: str = Field("http://localhost:19530", description="Full URL for Milvus/Zilliz server")
    token: str = Field(None, description="Token for Zilliz server / local setup defaults to None.")
    collection_name: str = Field("mem0", description="Name of the collection")
    embedding_model_dims: int = Field(1536, description="Dimensions of the embedding model")
    metric_type: str = Field("L2", description="Metric type for similarity search")
    db_name: str = Field("", description="Name of the database")

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")
