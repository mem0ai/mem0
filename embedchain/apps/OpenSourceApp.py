import logging
from typing import Optional

from embedchain.config import (BaseEmbedderConfig, BaseLlmConfig,
                               ChromaDbConfig, OpenSourceAppConfig)
from embedchain.embedchain import EmbedChain
from embedchain.embedder.gpt4all import GPT4AllEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.gpt4all import GPT4ALLLlm
from embedchain.vectordb.chroma import ChromaDB

gpt4all_model = None


@register_deserializable
class OpenSourceApp(EmbedChain):
    """
    The embedchain Open Source App.
    Comes preconfigured with the best open source LLM, embedding model, database.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.
    """

    def __init__(
        self,
        config: OpenSourceAppConfig = None,
        llm_config: BaseLlmConfig = None,
        chromadb_config: Optional[ChromaDbConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize a new `CustomApp` instance.
        Since it's opinionated you don't have to choose a LLM, database and embedder.
        However, you can configure those.

        :param config: Config for the app instance. This is the most basic configuration,
        that does not fall into the LLM, database or embedder category, defaults to None
        :type config: OpenSourceAppConfig, optional
        :param llm_config: Allows you to configure the LLM, e.g. how many documents to return.
        example: `from embedchain.config import LlmConfig`, defaults to None
        :type llm_config: BaseLlmConfig, optional
        :param chromadb_config: Allows you to configure the open source database,
        example: `from embedchain.config import ChromaDbConfig`, defaults to None
        :type chromadb_config: Optional[ChromaDbConfig], optional
        :param system_prompt: System prompt that will be provided to the LLM as such.
        Please don't use for the time being, as it's not supported., defaults to None
        :type system_prompt: Optional[str], optional
        :raises TypeError: `OpenSourceAppConfig` or `LlmConfig` invalid.
        """
        logging.info("Loading open source embedding model. This may take some time...")  # noqa:E501
        if not config:
            config = OpenSourceAppConfig()

        if not isinstance(config, OpenSourceAppConfig):
            raise TypeError(
                "OpenSourceApp needs a OpenSourceAppConfig passed to it. "
                "You can import it with `from embedchain.config import OpenSourceAppConfig`"
            )

        if not llm_config:
            llm_config = BaseLlmConfig(model="orca-mini-3b.ggmlv3.q4_0.bin")
        elif not isinstance(llm_config, BaseLlmConfig):
            raise TypeError(
                "The LlmConfig passed to OpenSourceApp is invalid. "
                "You can import it with `from embedchain.config import LlmConfig`"
            )
        elif not llm_config.model:
            llm_config.model = "orca-mini-3b.ggmlv3.q4_0.bin"

        llm = GPT4ALLLlm(config=llm_config)
        embedder = GPT4AllEmbedder(config=BaseEmbedderConfig(model="all-MiniLM-L6-v2"))
        logging.error("Successfully loaded open source embedding model.")
        database = ChromaDB(config=chromadb_config)

        super().__init__(config, llm=llm, db=database, embedder=embedder, system_prompt=system_prompt)
