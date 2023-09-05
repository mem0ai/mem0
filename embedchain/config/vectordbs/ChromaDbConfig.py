from typing import Optional

from embedchain.config.vectordbs.BaseVectorDbConfig import BaseVectorDbConfig
from embedchain.helper_classes.json_serializable import register_deserializable


@register_deserializable
class ChromaDbConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
        chroma_settings: Optional[dict] = None,
    ):
        """
        :param chroma_settings: Optional. Chroma settings for connection.
        """
        self.chroma_settings = chroma_settings
        super().__init__(collection_name=collection_name, dir=dir, host=host, port=port)
