import os
from typing import Optional

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class DeepInfraEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "BAAI/bge-large-en-v1.5"
            self.config.embedding_dims = 1024
            self.config.encoding_format = "float"

        api_key = self.config.api_key or os.getenv("DEEPINFRA_TOKEN")
        base_url = "https://api.deepinfra.com/v1/openai"
        self.client = OpenAI(api_key=api_key, base_url=base_url)

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
            self.client.embeddings.create(input=[text], model=self.config.model, encoding_format=self.config.encoding_format)
            .data[0]
            .embedding
        )
