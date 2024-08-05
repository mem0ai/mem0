import os
from typing import Optional
from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if self.config.lmstudio_base_url: # Use LM Studio
            if not self.config.model:
                self.config.model="nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
            if not self.config.embedding_dims:
                self.config.embedding_dims=768

            self.client = OpenAI(base_url=self.config.lmstudio_base_url, api_key=self.config.api_key)
        else:
            if not self.config.model:
                self.config.model="text-embedding-3-small"
            if not self.config.embedding_dims:
                self.config.embedding_dims=1536

            api_key = os.getenv("OPENAI_API_KEY") or self.config.api_key
            self.client = OpenAI(api_key=api_key)

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
