from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class QdrantDBConfig(BaseVectorDbConfig):
    """
    Config to initialize a qdrant client.
    :param: url. qdrant url or list of nodes url to be used for connection
    """

    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        hnsw_config: Optional[dict[str, any]] = None,
        quantization_config: Optional[dict[str, any]] = None,
        on_disk: Optional[bool] = None,
        **extra_params: dict[str, any],
    ):
        """
        Initializes a configuration class instance for a qdrant client.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        :param hnsw_config: Params for HNSW index
        :type hnsw_config: Optional[dict[str, any]], defaults to None
        :param quantization_config: Params for quantization, if None - quantization will be disabled
        :type quantization_config: Optional[dict[str, any]], defaults to None
        :param on_disk: If true - point`s payload will not be stored in memory.
                It will be read from the disk every time it is requested.
                This setting saves RAM by (slightly) increasing the response time.
                Note: those payload values that are involved in filtering and are indexed - remain in RAM.
        :type on_disk: bool, optional, defaults to None
        """
        self.hnsw_config = hnsw_config
        self.quantization_config = quantization_config
        self.on_disk = on_disk
        self.extra_params = extra_params
        super().__init__(collection_name=collection_name, dir=dir)
