import os
from typing import Optional

from voyageai import Client

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class VoyageAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "voyage-3"
        self.config.embedding_dims = self.config.embedding_dims

        api_key = self.config.api_key or os.getenv("VOYAGE_API_KEY")
        self.client = Client(api_key=api_key)

    def embed(self, text):
        """
        Get the embedding for the given text using VoyageAI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        return self.client.embed(
            texts=[text],
            model=self.config.model,
            output_dimension=self.config.embedding_dims,
        ).embeddings[0]
