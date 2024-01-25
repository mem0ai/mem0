from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class PineconeDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        index_name: Optional[str] = None,
        dir: Optional[str] = None,
        vector_dimension: int = 1536,
        metric: Optional[str] = "cosine",
        **extra_params: dict[str, any],
    ):
        self.metric = metric
        self.vector_dimension = vector_dimension
        self.extra_params = extra_params
        self.index_name = index_name or f"{collection_name}-{vector_dimension}".lower().replace("_", "-")
        super().__init__(collection_name=collection_name, dir=dir)
