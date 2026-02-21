import os
from typing import Literal, Optional

from sambanova import SambaNova

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class SambaNovaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "E5-Mistral-7B-Instruct"
        api_key = self.config.api_key or os.getenv("SAMBANOVA_API_KEY")
        self.config.embedding_dims = self.config.embedding_dims or 4096
        self.client = SambaNova(api_key=api_key)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using SambaNova.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """

        return self.client.embeddings.create(model=self.config.model, input=text).data[0].embedding
