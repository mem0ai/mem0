from typing import Optional

from embedchain.config import (AppConfig, BaseEmbedderConfig, BaseLlmConfig,
                               ChromaDbConfig)
from embedchain.embedchain import EmbedChain
from embedchain.embedder.openai_embedder import OpenAiEmbedder
from embedchain.helper_classes.json_serializable import register_deserializable
from embedchain.llm.openai_llm import OpenAiLlm
from embedchain.vectordb.chroma_db import ChromaDB


@register_deserializable
class App(EmbedChain):
    """
    The EmbedChain app in it's simplest and most straightforward form.
    An opinionated choice of LLM, vector database and embedding model.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.
    """

    def __init__(
        self,
        config: AppConfig = None,
        llm_config: BaseLlmConfig = None,
        chromadb_config: Optional[ChromaDbConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize a new `CustomApp` instance. You only have a few choices to make.

        :param config: Config for the app instance.
        This is the most basic configuration, that does not fall into the LLM, database or embedder category,
        defaults to None
        :type config: AppConfig, optional
        :param llm_config: Allows you to configure the LLM, e.g. how many documents to return,
        example: `from embedchain.config import LlmConfig`, defaults to None
        :type llm_config: BaseLlmConfig, optional
        :param chromadb_config: Allows you to configure the vector database,
        example: `from embedchain.config import ChromaDbConfig`, defaults to None
        :type chromadb_config: Optional[ChromaDbConfig], optional
        :param system_prompt: System prompt that will be provided to the LLM as such, defaults to None
        :type system_prompt: Optional[str], optional
        """
        if config is None:
            config = AppConfig()

        llm = OpenAiLlm(config=llm_config)
        embedder = OpenAiEmbedder(config=BaseEmbedderConfig(model="text-embedding-ada-002"))
        database = ChromaDB(config=chromadb_config)

        super().__init__(config, llm, db=database, embedder=embedder, system_prompt=system_prompt)
