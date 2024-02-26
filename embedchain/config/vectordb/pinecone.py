import os
from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class PineconeDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        index_name: Optional[str] = None,
        api_key: Optional[str] = None,
        vector_dimension: int = 1536,
        metric: Optional[str] = "cosine",
        pod_config: Optional[dict[str, any]] = None,
        serverless_config: Optional[dict[str, any]] = None,
        hybrid_search: bool = False,
        bm25_encoder: any = None,
        **extra_params: dict[str, any],
    ):
        self.metric = metric
        self.api_key = api_key
        self.index_name = index_name
        self.vector_dimension = vector_dimension
        self.extra_params = extra_params
        self.hybrid_search = hybrid_search
        self.bm25_encoder = bm25_encoder
        if pod_config is None and serverless_config is None:
            # If no config is provided, use the default pod spec config
            pod_environment = os.environ.get("PINECONE_ENV", "gcp-starter")
            self.pod_config = {"environment": pod_environment, "metadata_config": {"indexed": ["*"]}}
        else:
            self.pod_config = pod_config
        self.serverless_config = serverless_config

        if self.pod_config and self.serverless_config:
            raise ValueError("Only one of pod_config or serverless_config can be provided.")

        if self.hybrid_search and self.metric != "dotproduct":
            raise ValueError(
                "Hybrid search is only supported with dotproduct metric in Pinecone. See full docs here: https://docs.pinecone.io/docs/hybrid-search#limitations"
            )  # noqa:E501

        super().__init__(collection_name=self.index_name, dir=None)
