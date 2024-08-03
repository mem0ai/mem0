from typing import Optional
from abc import ABC, abstractmethod

from mem0.configs.embeddings.base import BaseEmbedderConfig


class EmbeddingBase(ABC):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        """Initialize a base LLM class

        :param config: Embedder configuration option class, defaults to None
        :type config: Optional[BaseEmbedderConfig], optional
        """
        if config is None:
            self.config = BaseEmbedderConfig()
        else:
            self.config = config

    @abstractmethod
    def embed(self, text):
        """
        Get the embedding for the given text.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        pass
