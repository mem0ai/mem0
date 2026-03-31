from abc import ABC, abstractmethod
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig


class EmbeddingBase(ABC):
    """Initialized a base embedding class

    :param config: Embedding configuration option class, defaults to None
    :type config: Optional[BaseEmbedderConfig], optional
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        if config is None:
            self.config = BaseEmbedderConfig()
        else:
            self.config = config

    @abstractmethod
    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None) -> list:
        """
        Get the embedding for the given text.

        Args:
            text: The text to embed.
            memory_action: The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.

        Returns:
            The embedding vector as a list of floats.
        """
        pass
