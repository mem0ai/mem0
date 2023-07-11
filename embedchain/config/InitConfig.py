import logging
import os

from chromadb.utils import embedding_functions

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

        self.ef = ef
        self.db = db
        return

    def _set_embedding_function(self, ef):
        self.ef = ef
        return

    def _set_embedding_function_to_default(self):
        """
        Sets embedding function to default (`text-embedding-ada-002`).

        :raises ValueError: If the template is not valid as template should contain
        $context and $query
        """
        if (
            os.getenv("OPENAI_API_KEY") is None
            or os.getenv("OPENAI_ORGANIZATION") is None
        ):
            raise ValueError(
                "OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided"  # noqa:E501
            )
        self.ef = embedding_functions.OpenAIEmbeddingFunction(
            api_key=os.getenv("OPENAI_API_KEY"),
            organization_id=os.getenv("OPENAI_ORGANIZATION"),
            model_name="text-embedding-ada-002",
        )
        return

    def _set_db(self, db):
        if db:
            self.db = db
        return

    def _set_db_to_default(self):
        """
        Sets database to default (`ChromaDb`).
        """
        from embedchain.vectordb.chroma_db import ChromaDB

        self.db = ChromaDB(ef=self.ef)

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
