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

    def add(self, data, config: AddConfig = None):
        """Add data to the bot"""
        config = config if config else AddConfig()
        self.app.add(data, config=config)

    def query(self, query, config: LlmConfig = None):
        """Query bot"""
        config = config
        return self.app.query(query, config=config)

    def start(self):
        """Start the bot's functionality."""
        raise NotImplementedError("Subclasses must implement the start method.")
