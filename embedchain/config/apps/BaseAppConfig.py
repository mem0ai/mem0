import logging

from embedchain.config.BaseConfig import BaseConfig


class BaseAppConfig(BaseConfig):
    """
    Parent config to initialize an instance of `App`, `OpenSourceApp` or `CustomApp`.
    """

    def __init__(self, log_level=None, embedding_fn=None, db=None, host=None, port=None, id=None):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param embedding_fn: Embedding function to use.
        :param db: Optional. (Vector) database instance to use for embeddings.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        """
        self._setup_logging(log_level)

        self.db = db if db else BaseAppConfig.default_db(embedding_fn=embedding_fn, host=host, port=port)
        self.id = id
        return

    @staticmethod
    def default_db(embedding_fn, host, port):
        """
        Sets database to default (`ChromaDb`).

        :param embedding_fn: Embedding function to use in database.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        :returns: Default database
        :raises ValueError: BaseAppConfig knows no default embedding function.
        """
        if embedding_fn is None:
            raise ValueError("ChromaDb cannot be instantiated without an embedding function")
        from embedchain.vectordb.chroma_db import ChromaDB

        return ChromaDB(embedding_fn=embedding_fn, host=host, port=port)

    def _setup_logging(self, debug_level):
        level = logging.WARNING  # Default level
        if debug_level is not None:
            level = getattr(logging, debug_level.upper(), None)
            if not isinstance(level, int):
                raise ValueError(f"Invalid log level: {debug_level}")

        logging.basicConfig(format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", level=level)
        self.logger = logging.getLogger(__name__)
        return
