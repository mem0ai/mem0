from typing import Optional

from embedchain.config.base_config import BaseConfig


class BaseVectorDbConfig(BaseConfig):
    def __init__(
        self,
        collection_name: Optional[str] = None,
        dir: str = "db",
        host: Optional[str] = None,
        port: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for the vector database.

        :param collection_name: Default name for the collection, defaults to None
        :type collection_name: Optional[str], optional
        :param dir: Path to the database directory, where the database is stored, defaults to "db"
        :type dir: str, optional
        :param host: Database connection remote host. Use this if you run Embedchain as a client, defaults to None
        :type host: Optional[str], optional
        :param host: Database connection remote port. Use this if you run Embedchain as a client, defaults to None
        :type port: Optional[str], optional
        """
        self.collection_name = collection_name or "embedchain_store"
        self.dir = dir
        self.host = host
        self.port = port
