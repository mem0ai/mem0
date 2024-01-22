from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class PineconeDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        api_key: Optional[str] = None,
        vector_dimension: int = 1536,
        metric: Optional[str] = "cosine",
        pod_config: Optional[dict[str, any]] = None,
        serverless_config: Optional[dict[str, any]] = None,
        **extra_params: dict[str, any],
    ):
        self.metric = metric
        self.api_key = api_key
        self.vector_dimension = vector_dimension
        self.extra_params = extra_params
        if pod_config is None and serverless_config is None:
            # If no config is provided, use the default pod spec config
            self.pod_config = {"environment": "gcp-starter", "metadata_config": {"indexed": ["*"]}}
        else:
            self.pod_config = pod_config
        self.serverless_config = serverless_config

        if self.pod_config and self.serverless_config:
            raise ValueError("Only one of pod_config or serverless_config can be provided.")

        super().__init__(collection_name=collection_name, dir=None)
