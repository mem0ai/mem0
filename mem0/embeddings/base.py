from abc import ABC, abstractmethod
from typing import List, Literal, Optional

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
    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]]):
        """
        Get the embedding for the given text.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        pass

    def embed_multimodal(self, inputs: list, memory_action: Optional[Literal["add", "search", "update"]] = None) -> list:
        """
        Get the embedding for multimodal inputs (text + images).

        This is an optional method that providers can implement to support multimodal embeddings.
        By default, it raises NotImplementedError.

        Args:
            inputs (list): List of inputs (strings or PIL Image objects).
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        Raises:
            NotImplementedError: If the provider does not support multimodal embeddings.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support multimodal embeddings")

    def embed_contextualized(
        self, chunks: List[List[str]], memory_action: Optional[Literal["add", "search", "update"]] = None
    ) -> List[list]:
        """
        Get context-aware embeddings for document chunks.

        This is an optional method that providers can implement to support contextualized chunk embeddings.
        Each inner list should contain chunks from a single document, ordered by position.
        The model encodes chunks together to preserve relational context.

        Args:
            chunks (List[List[str]]): List of lists, where each inner list contains chunks from one document.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            List[list]: List of embedding vectors (one per chunk).
        Raises:
            NotImplementedError: If the provider does not support contextualized embeddings.
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support contextualized embeddings")
