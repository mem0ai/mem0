from typing import Optional

from embedchain.config.vector_db.base import BaseVectorDbConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class ChromaDbConfig(BaseVectorDbConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: Optional[str] = None,
        host: Optional[str] = None,
        port: Optional[str] = None,
        batch_size: Optional[int] = 100,
        allow_reset=False,
        chroma_settings: Optional[dict] = None,
    ):
        """
        Initializes a configuration class instance for ChromaDB.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to None
        :type dir: Optional[str], optional
        :param host: Database connection remote host. Use this if you run Embedchain as a client, defaults to None
        :type host: Optional[str], optional
        :param port: Database connection remote port. Use this if you run Embedchain as a client, defaults to None
        :type port: Optional[str], optional
        :param batch_size: Number of items to insert in one batch, defaults to 100
        :type batch_size: Optional[int], optional
        :param allow_reset: Resets the database. defaults to False
        :type allow_reset: bool
        :param chroma_settings: Chroma settings dict, defaults to None
        :type chroma_settings: Optional[dict], optional
        """

        self.chroma_settings = chroma_settings
        self.allow_reset = allow_reset
        self.batch_size = batch_size
        super().__init__(collection_name=collection_name, dir=dir, host=host, port=port)
