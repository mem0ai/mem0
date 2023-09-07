from typing import Any

from embedchain import CustomApp
from embedchain.config import AddConfig, CustomAppConfig, LlmConfig
from embedchain.embedder.openai_embedder import OpenAiEmbedder
from embedchain.helper_classes.json_serializable import (
    JSONSerializable, register_deserializable)
from embedchain.llm.openai_llm import OpenAiLlm
from embedchain.vectordb.chroma_db import ChromaDB


@register_deserializable
class BaseBot(JSONSerializable):
    def __init__(self):
        self.app = CustomApp(config=CustomAppConfig(), llm=OpenAiLlm(), db=ChromaDB(), embedder=OpenAiEmbedder())

    def add(self, data: Any, config: AddConfig = None):
        """
        Add data to the bot (to the vector database).
        Auto-dectects type only, so some data types might not be usable.

        :param data: data to embed
        :type data: Any
        :param config: configuration class instance, defaults to None
        :type config: AddConfig, optional
        """
        config = config if config else AddConfig()
        self.app.add(data, config=config)

    def query(self, query: str, config: LlmConfig = None) -> str:
        """
        Query the bot

        :param query: the user query
        :type query: str
        :param config: configuration class instance, defaults to None
        :type config: LlmConfig, optional
        :return: Answer
        :rtype: str
        """
        config = config
        return self.app.query(query, config=config)

    def start(self):
        """Start the bot's functionality."""
        raise NotImplementedError("Subclasses must implement the start method.")
