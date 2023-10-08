from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class WeaviateDbConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
    ):
        super().__init__(collection_name=collection_name, dir=dir)
