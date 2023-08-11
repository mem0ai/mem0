from typing import Optional

from chromadb.utils import embedding_functions

from .BaseAppConfig import BaseAppConfig


class OpenSourceAppConfig(BaseAppConfig):
    """
    Config to initialize an embedchain custom `OpenSourceApp` instance, with extra config options.
    """

    def __init__(
        self,
        log_level=None,
        host=None,
        port=None,
        id=None,
        collection_name=None,
        collect_metrics: Optional[bool] = None,
        model=None,
    ):
        """
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param collection_name: Optional. Collection name for the database.
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        :param collect_metrics: Defaults to True. Send anonymous telemetry to improve embedchain.
        :param model: Optional. GPT4ALL uses the model to instantiate the class.
        So unlike `App`, it has to be provided before querying.
        """
        self.model = model or "orca-mini-3b.ggmlv3.q4_0.bin"

        super().__init__(
            log_level=log_level,
            embedding_fn=OpenSourceAppConfig.default_embedding_function(),
            host=host,
            port=port,
            id=id,
            collection_name=collection_name,
            collect_metrics=collect_metrics,
        )

    @staticmethod
    def default_embedding_function():
        """
        Sets embedding function to default (`all-MiniLM-L6-v2`).

        :returns: The default embedding function
        """
        return embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
