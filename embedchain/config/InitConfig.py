import logging
import os

from embedchain.config.BaseConfig import BaseConfig


class InitConfig(BaseConfig):
    """
    Config to initialize an embedchain `App` instance.
    """

    def __init__(self, log_level=None, ef=None, db=None, host=None, port=None):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param ef: Optional. Embedding function to use.
        :param db: Optional. (Vector) database to use for embeddings.
        """
        self._setup_logging(log_level)

        # Embedding Function
        if ef is None:
            from chromadb.utils import embedding_functions

            self.ef = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name="text-embedding-ada-002",
            )
        else:
            self.ef = ef

        if db is None:
            from embedchain.vectordb.chroma_db import ChromaDB

            self.db = ChromaDB(ef=self.ef, host=host, port=port)
        else:
            self.db = db

        return

    def _set_embedding_function(self, ef):
        self.ef = ef
        return

    def _setup_logging(self, debug_level):
        level = logging.WARNING  # Default level
        if debug_level is not None:
            level = getattr(logging, debug_level.upper(), None)
            if not isinstance(level, int):
                raise ValueError(f"Invalid log level: {debug_level}")

        logging.basicConfig(
            format="%(asctime)s [%(name)s] [%(levelname)s] %(message)s", level=level
        )
        self.logger = logging.getLogger(__name__)
        return
