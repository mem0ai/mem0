import functools
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
        self._cache = {}

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text with LRU caching.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        # Simple cache key: (text, memory_action)
        cache_key = (text, memory_action)
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        embedding = self._embed(text, memory_action)
        
        # Simple cache management (limit to 1000 items)
        if len(self._cache) > 1000:
            self._cache.pop(next(iter(self._cache)))
        
        self._cache[cache_key] = embedding
        return embedding

    @abstractmethod
    def _embed(self, text, memory_action: Optional[Literal["add", "search", "update"]]):
        """
        Actual implementation of the embedding logic.
        """
        pass
