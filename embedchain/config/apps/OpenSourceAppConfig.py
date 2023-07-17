from chromadb.utils import embedding_functions

from .BaseAppConfig import BaseAppConfig


class OpenSourceAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `OpenSourceApp` instance, with extra config options.
    """

    def __init__(self, log_level=None, host=None, port=None, id=None):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        """
        super().__init__(
            log_level=log_level, ef=OpenSourceAppConfig.default_embedding_function(), host=host, port=port, id=id
        )

    @staticmethod
    def default_embedding_function():
        """
        Sets embedding function to default (`all-MiniLM-L6-v2`).

        :returns: The default embedding function
        """
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
