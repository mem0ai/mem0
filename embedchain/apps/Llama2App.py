import logging
from typing import Optional

from embedchain.apps.CustomApp import CustomApp
from embedchain.config import CustomAppConfig
from embedchain.embedder.openai import OpenAiEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.llm.llama2 import Llama2Llm
from embedchain.vectordb.chroma import ChromaDB


@register_deserializable
class Llama2App(CustomApp):
    """
    The EmbedChain Llama2App class.

    Methods:
    add(source, data_type): adds the data from the given URL to the vector db.
    query(query): finds answer to the given query using vector database and LLM.
    chat(query): finds answer to the given query using vector database and LLM, with conversation history.
    """

    def __init__(self, load: str = "config.yaml", config: CustomAppConfig = None, system_prompt: Optional[str] = None):
        """
        :param load: Path to a yaml config that you can use to configure whole app.
        You can generate a template in your working directory with `App.generate_default_config()`, defaults to `config.yaml`.
        :type load: str
        :param config: CustomAppConfig instance to load as configuration. Optional.
        :param system_prompt: System prompt string. Optional.
        """

        if isinstance(load, CustomAppConfig):
            logging.warning(
                "The signature of this function has changed. `config` is now the second argument for `Llama2App`."
                "We are swapping them for you, but we won't do this forever, please update your code."
            )
            config = load
            load = None

        if config is None:
            config = CustomAppConfig()

        super().__init__(
            load, config=config, llm=Llama2Llm(), db=ChromaDB(), embedder=OpenAiEmbedder(), system_prompt=system_prompt
        )
