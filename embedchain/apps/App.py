from typing import Optional

from embedchain.config import AppConfig, BaseEmbedderConfig, ChromaDbConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.openai_embedder import OpenAiEmbedder
from embedchain.llm.openai_llm import OpenAiLlm
from embedchain.vectordb.chroma_db import ChromaDB


class App(EmbedChain):
    """
    The EmbedChain app.
    Has two functions: add and query.

    adds(data_type, url): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    dry_run(query): test your prompt without consuming tokens.
    """

    def __init__(self, config: AppConfig = None, chromadb_config: Optional[ChromaDbConfig] = None):
        """
        :param config: AppConfig instance to load as configuration. Optional.
        """
        if config is None:
            config = AppConfig()

        llm = OpenAiLlm()
        embedder = OpenAiEmbedder(config=BaseEmbedderConfig(model="text-embedding-ada-002"))
        database = ChromaDB(config=chromadb_config, embedder=embedder)

        super().__init__(config, llm, db=database, embedder=embedder)
