import os
from typing import Optional

import google.generativeai as genai

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "models/text-embedding-004"
        self.config.embedding_dims = self.config.embedding_dims or 768

        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")

        genai.configure(api_key=api_key)

    def embed(self, text):
        """
        Get the embedding for the given text using Google Generative AI.
        Args:
            text (str): The text to embed.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        response = genai.embed_content(model=self.config.model, content=text)
        return response["embedding"]
