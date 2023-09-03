from embedchain.config import CustomAppConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base_embedder import BaseEmbedder
from embedchain.llm.base_llm import BaseLlm
from embedchain.vectordb.base_vector_db import BaseVectorDB


class CustomApp(EmbedChain):
    """
    The custom EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(
        self,
        config: CustomAppConfig = None,
        llm: BaseLlm = None,
        db: BaseVectorDB = None,
        embedder: BaseEmbedder = None,
    ):
        """
        :param config: Optional. `CustomAppConfig` instance to load as configuration.
        :raises ValueError: Config must be provided for custom app
        """
        if config is None:
            raise ValueError("Config must be provided for custom app")
        if llm is None:
            raise ValueError("LLM must be provided for custom app")
        if db is None:
            raise ValueError("Database must be provided for custom app")
        if embedder is None:
            raise ValueError("Embedder must be provided for custom app")

        super().__init__(config=config, llm=llm, db=db, embedder=embedder)
