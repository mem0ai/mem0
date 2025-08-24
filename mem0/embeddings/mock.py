from typing import Literal, Optional

from mem0.embeddings.base import EmbeddingBase


class MockEmbeddings(EmbeddingBase):
    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Generate a mock embedding with dimension of 10.
        """
        return [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
