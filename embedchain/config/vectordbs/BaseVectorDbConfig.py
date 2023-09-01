from typing import Callable, Optional

from embedchain.config.BaseConfig import BaseConfig
from embedchain.models.VectorDimensions import VectorDimensions


class BaseVectorDbConfig(BaseConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        embedding_fn: Callable[[list[str]], list[str]] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
        vector_dim: Optional[VectorDimensions] = None,
    ):
        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")

        self.collection_name = collection_name or "embedchain_store"
        self.dir = dir or "db"
        self.embedding_fn = embedding_fn
        self.host = host
        self.port = port
        self.vector_dim = vector_dim
