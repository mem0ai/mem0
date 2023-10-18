from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helper.json_serializable import register_deserializable
from typing import Optional, Dict


@register_deserializable
class QdrantDBConfig(BaseVectorDbConfig):
    """
    Config to initialize an qdrant client.
    :param url. qdrant url or list of nodes url to be used for connection
    """

    def __init__(self, collection_name: Optional[str] = None, dir: Optional[str] = None,
                 hnsw_config: Optional[Dict[str, any]] = None, quantization_config: Optional[Dict[str, any]] = None,
                 on_disk: Optional[bool] = None, **extra_params: Dict[str, any]):
        self.hnsw_config = hnsw_config
        self.quantization_config = quantization_config
        self.on_disk = on_disk
        self.extra_params = extra_params
        super().__init__(collection_name=collection_name, dir=dir)
