from typing import Dict, Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class WeaviateDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        **extra_params: Dict[str, any],
    ):
        self.extra_params = extra_params
        super().__init__(collection_name=collection_name, dir=dir)
