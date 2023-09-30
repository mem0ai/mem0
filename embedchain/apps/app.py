import logging
from typing import Optional

from embedchain.config import (AppConfig, BaseEmbedderConfig, BaseLlmConfig,
                               ChromaDbConfig)
from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.embedder.openai import OpenAIEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm
from embedchain.llm.openai import OpenAILlm
from embedchain.vectordb.base import BaseVectorDB
from embedchain.vectordb.chroma import ChromaDB


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
        config: Optional[AppConfig] = None,
        llm: BaseLlm = None,
        llm_config: Optional[BaseLlmConfig] = None,
        db: BaseVectorDB = None,
        db_config: Optional[BaseVectorDbConfig] = None,
        embedder: BaseEmbedder = None,
        embedder_config: Optional[BaseEmbedderConfig] = None,
        chromadb_config: Optional[ChromaDbConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize a new `App` instance.

        :param config: Config for the app instance., defaults to None
        :type config: Optional[AppConfig], optional
        :param llm:  LLM Class instance. example: `from embedchain.llm.openai import OpenAILlm`, defaults to OpenAiLlm
        :type llm: BaseLlm, optional
        :param llm_config: Allows you to configure the LLM, e.g. how many documents to return,
        example: `from embedchain.config import LlmConfig`, defaults to None
        :type llm_config: Optional[BaseLlmConfig], optional
        :param db: The database to use for storing and retrieving embeddings,
        example: `from embedchain.vectordb.chroma_db import ChromaDb`, defaults to ChromaDb
        :type db: BaseVectorDB, optional
        :param db_config: Allows you to configure the vector database,
        example: `from embedchain.config import ChromaDbConfig`, defaults to None
        :type db_config: Optional[BaseVectorDbConfig], optional
        :param embedder: The embedder (embedding model and function) use to calculate embeddings.
        example: `from embedchain.embedder.gpt4all_embedder import GPT4AllEmbedder`, defaults to OpenAIEmbedder
        :type embedder: BaseEmbedder, optional
        :param embedder_config: Allows you to configure the Embedder.
        example: `from embedchain.config import BaseEmbedderConfig`, defaults to None
        :type embedder_config: Optional[BaseEmbedderConfig], optional
        :param chromadb_config: Deprecated alias of `db_config`, defaults to None
        :type chromadb_config: Optional[ChromaDbConfig], optional
        :param system_prompt: System prompt that will be provided to the LLM as such, defaults to None
        :type system_prompt: Optional[str], optional
        :raises TypeError: LLM, database or embedder or their config is not a valid class instance.
        """
        # Overwrite deprecated arguments
        if chromadb_config:
            logging.warning(
                "DEPRECATION WARNING: Please use `db_config` argument instead of `chromadb_config`."
                "`chromadb_config` will be removed in a future release."
            )
            db_config = chromadb_config

        # Type check configs
        if config and not isinstance(config, AppConfig):
            raise TypeError(
                "Config is not a `AppConfig` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if llm_config and not isinstance(llm_config, BaseLlmConfig):
            raise TypeError(
                "`llm_config` is not a `BaseLlmConfig` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if db_config and not isinstance(db_config, BaseVectorDbConfig):
            raise TypeError(
                "`db_config` is not a `BaseVectorDbConfig` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if embedder_config and not isinstance(embedder_config, BaseEmbedderConfig):
            raise TypeError(
                "`embedder_config` is not a `BaseEmbedderConfig` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )

        # Assign defaults
        if config is None:
            config = AppConfig()
        if llm is None:
            llm = OpenAILlm(config=llm_config)
        if db is None:
            db = ChromaDB(config=db_config)
        if embedder is None:
            embedder = OpenAIEmbedder(config=embedder_config)

        # Type check assignments
        if not isinstance(llm, BaseLlm):
            raise TypeError(
                "LLM is not a `BaseLlm` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if not isinstance(db, BaseVectorDB):
            raise TypeError(
                "Database is not a `BaseVectorDB` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        if not isinstance(embedder, BaseEmbedder):
            raise TypeError(
                "Embedder is not a `BaseEmbedder` instance. "
                "Please make sure the type is right and that you are passing an instance."
            )
        super().__init__(config, llm=llm, db=db, embedder=embedder, system_prompt=system_prompt)
