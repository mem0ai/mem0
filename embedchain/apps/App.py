import logging
from typing import Optional

from embedchain.config import (AppConfig, BaseEmbedderConfig, BaseLlmConfig,
                               ChromaDbConfig)
from embedchain.embedchain import EmbedChain
from embedchain.embedder.openai import OpenAiEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.openai import OpenAILlm
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
        config: str = "config.yaml",
        app_config: Optional[AppConfig] = None,
        llm_config: Optional[BaseLlmConfig] = None,
        chromadb_config: Optional[ChromaDbConfig] = None,
        system_prompt: Optional[str] = None,
    ):
        """
        Initialize a new `CustomApp` instance. You only have a few choices to make.

        :param config: Path to a yaml config that you can use to configure whole app.
        You can generate a template in your working directory with `App.generate_default_config()`,
        defaults to `config.yaml`.
        :type config: str
        :param app_config: Config for the app instance.
        This is the most basic configuration, that does not fall into the LLM, database or embedder category,
        defaults to None
        :type app_config: AppConfig, optional
        :param llm_config: Allows you to configure the LLM, e.g. how many documents to return,
        example: `from embedchain.config import LlmConfig`, defaults to None
        :type llm_config: BaseLlmConfig, optional
        :param chromadb_config: Allows you to configure the vector database,
        example: `from embedchain.config import ChromaDbConfig`, defaults to None
        :type chromadb_config: Optional[ChromaDbConfig], optional
        :param system_prompt: System prompt that will be provided to the LLM as such, defaults to None
        :type system_prompt: Optional[str], optional
        """
        if isinstance(config, AppConfig):
            logging.warning(
                "The signature of this function has changed. `config` is now the second argument for `App`."
                "We are swapping them for you, but we won't do this forever, please update your code."
            )
            app_config = config
            config = None

        if config and (app_config or llm_config or chromadb_config or system_prompt):
            raise ValueError("You cannot use a yaml and a class based config simultaneously. We are working on this.")

        if app_config is None:
            app_config = AppConfig()

        llm = OpenAILlm(config=llm_config)
        embedder = OpenAiEmbedder(config=BaseEmbedderConfig(model="text-embedding-ada-002"))
        database = ChromaDB(config=chromadb_config)

        super().__init__(
            config=config, app_config=app_config, llm=llm, db=database, embedder=embedder, system_prompt=system_prompt
        )
