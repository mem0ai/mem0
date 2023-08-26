import os
from typing import Optional

try:
    from chromadb.utils import embedding_functions
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.utils import embedding_functions

from .BaseAppConfig import BaseAppConfig


class RemoteLLMConfig(BaseAppConfig):
    """
    Config to initialize an embedchain `RemoteLLMApp` instance, with extra config options.
    """

    def __init__(
        self,
        endpoint_url,
        response_key="generated_text",
        log_level=None,
        host=None,
        port=None,
        collection_name=None,
        collect_metrics: Optional[bool] = False,
    ):
        """
        :param endpoint_url: URL of the Remote LLLM inference service.
        :param response_key: The key in the response that returns the actual response.
        :param log_level: Optional. (String) Debug level
        ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'].
        :param host: Optional. Hostname for the database server.
        :param port: Optional. Port for the database server.
        :param id: Optional. ID of the app. Document metadata will have this id.
        :param collection_name: Optional. Collection name for the database.
        :param collect_metrics: Defaults to False. RemoteLLM is usually used by enterprise who don't want to send anonymous telemetry.
        """
        super().__init__(
            log_level=log_level,
            embedding_fn=RemoteLLMConfig.default_embedding_function(),
            host=host,
            port=port,
            id=id,
            collection_name=collection_name,
            collect_metrics=collect_metrics,
        )
        self.endpoint_url = endpoint_url
        self.response_key = response_key

    @staticmethod
    def default_embedding_function():
        """
        Sets embedding function to default (`all-MiniLM-L6-v2`).

        :returns: The default embedding function
        """
        try:
            return embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
        except ValueError as e:
            print(e)
            raise ModuleNotFoundError(
                "The remote LLM app requires extra dependencies. Install with `pip install embedchain[opensource]`"
            ) from None
