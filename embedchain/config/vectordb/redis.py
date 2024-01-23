from typing import Optional

from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class RedisDBConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        redis_url: Optional[str] = None,
        vector_config: Optional[dict] = None,
    ):
        """
        Initializes a configuration class instance for RedisDB.
        :param collection_name: Default name for the index, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the redis database
        :type dir: Optional[str], optional
        :param vector_dimension: Dimension for the vector field
        :type vector_dimesion: Optional[int], optional
        """
        self.redis_url = redis_url or "redis://localhost:6379"
        self.vector_config = vector_config
        self.id_field_name = "id"
        self.text_field_name = "text"
        self.metadata_field_name = "metadata"
        self.vector_field_name = "vector"
        super().__init__(collection_name=collection_name)
