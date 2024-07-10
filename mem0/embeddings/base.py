from abc import ABC, abstractmethod


class EmbeddingBase(ABC):
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
