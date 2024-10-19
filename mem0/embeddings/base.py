from abc import ABC, abstractmethod
from typing import Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.utils.concurrency import run_in_executor


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
    
    async def aembed(self, text):
        """Async version of the embed method.

        The default implementation delegates to the synchronous generate_response method using
        `run_in_executor`. Subclasses that need to provide a true async implementation
        should override this method to reduce the overhead of using `run_in_executor`.
        """
        return await run_in_executor(
            None,
            self.embed,
            text
        )

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
