from typing import Optional

import yaml

from embedchain.client import Client
from embedchain.config import (AppConfig, BaseEmbedderConfig, BaseLlmConfig,
                               ChunkerConfig)
from embedchain.config.vectordb.base import BaseVectorDbConfig
from embedchain.embedchain import EmbedChain
from embedchain.embedder.base import BaseEmbedder
from embedchain.embedder.openai import OpenAIEmbedder
from embedchain.factory import EmbedderFactory, LlmFactory, VectorDBFactory
from embedchain.helpers.json_serializable import register_deserializable
from embedchain.llm.base import BaseLlm
from embedchain.llm.openai import OpenAILlm
from embedchain.utils import validate_yaml_config
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
        system_prompt: Optional[str] = None,
        chunker: Optional[ChunkerConfig] = None,
    ):
        """
        Initialize a new `App` instance.

        :param config: Config for the app instance., defaults to None
        :type config: Optional[AppConfig], optional
        :param llm:  LLM Class instance. example: `from embedchain.llm.openai import OpenAILlm`, defaults to OpenAiLlm
        :type llm: BaseLlm, optional
        :param llm_config: Allows you to configure the LLM, e.g. how many documents to return,
        example: `from embedchain.config import BaseLlmConfig`, defaults to None
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
        :param system_prompt: System prompt that will be provided to the LLM as such, defaults to None
        :type system_prompt: Optional[str], optional
        :raises TypeError: LLM, database or embedder or their config is not a valid class instance.
        """
        # Setup user directory if it doesn't exist already
        Client.setup_dir()

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

        self.chunker = None
        if chunker:
            self.chunker = ChunkerConfig(**chunker)
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

    @classmethod
    def from_config(cls, yaml_path: str):
        """
        Instantiate an App object from a YAML configuration file.

        :param yaml_path: Path to the YAML configuration file.
        :type yaml_path: str
        :return: An instance of the App class.
        :rtype: App
        """
        # Setup user directory if it doesn't exist already
        Client.setup_dir()

        with open(yaml_path, "r") as file:
            config_data = yaml.safe_load(file)

        try:
            validate_yaml_config(config_data)
        except Exception as e:
            raise Exception(f"❌ Error occurred while validating the YAML config. Error: {str(e)}")

        app_config_data = config_data.get("app", {})
        llm_config_data = config_data.get("llm", {})
        db_config_data = config_data.get("vectordb", {})
        embedding_model_config_data = config_data.get("embedding_model", config_data.get("embedder", {}))
        chunker_config_data = config_data.get("chunker", {})

        app_config = AppConfig(**app_config_data.get("config", {}))

        llm_provider = llm_config_data.get("provider", "openai")
        llm = LlmFactory.create(llm_provider, llm_config_data.get("config", {}))

        db_provider = db_config_data.get("provider", "chroma")
        db = VectorDBFactory.create(db_provider, db_config_data.get("config", {}))

        embedder_provider = embedding_model_config_data.get("provider", "openai")
        embedder = EmbedderFactory.create(embedder_provider, embedding_model_config_data.get("config", {}))
        return cls(config=app_config, llm=llm, db=db, embedder=embedder, chunker=chunker_config_data)
