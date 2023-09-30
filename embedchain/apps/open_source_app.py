import logging
from typing import Optional

from embedchain.apps.app import App
from embedchain.config import (BaseLlmConfig, ChromaDbConfig,
                               OpenSourceAppConfig)
from embedchain.embedder.gpt4all import GPT4AllEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.gpt4all import GPT4ALLLlm
from embedchain.vectordb.chroma import ChromaDB

gpt4all_model = None


@register_deserializable
class OpenSourceApp(App):
    """
    The embedchain Open Source App.
    Comes preconfigured with the best open source LLM, embedding model, database.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.

    .. deprecated:: 0.0.64
    Use `App` instead.
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

        .. deprecated:: 0.0.64
        Use `App` instead.

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
        logging.warning(
            "DEPRECATION WARNING: Please use `App` instead of `OpenSourceApp`."
            "`OpenSourceApp` will be removed in a future release."
            "Please refer to https://docs.embedchain.ai/advanced/app_types#customapp for instructions."
        )

        super().__init__(
            config=config,
            llm=GPT4ALLLlm(config=llm_config),
            db=ChromaDB(config=chromadb_config),
            embedder=GPT4AllEmbedder(),
            system_prompt=system_prompt,
        )
