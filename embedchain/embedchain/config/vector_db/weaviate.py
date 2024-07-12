from typing import Optional

from embedchain.config.vector_db.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class WeaviateDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        batch_size: Optional[int] = 100,
        **extra_params: dict[str, any],
    ):
        self.batch_size = batch_size
        self.extra_params = extra_params
        super().__init__(collection_name=collection_name, dir=dir)
