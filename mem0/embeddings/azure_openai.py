import os
from typing import Optional

from openai import AzureOpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class AzureOpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if self.config.model is None:
            self.config.model = "text-embedding-3-small"
        if self.config.embedding_dims is None:
            self.config.embedding_dims = 1536

        api_key = os.getenv("AZURE_OPENAI_API_KEY") or self.config.api_key
        self.client = AzureOpenAI(api_key=api_key)

    def embed(self, text):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0]
            .embedding
        )
