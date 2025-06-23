import os
from typing import Literal, Optional

import google.genai as genai

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "models/text-embedding-004"
        self.config.embedding_dims = self.config.embedding_dims or self.config.output_dimensionality or 768

        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")

        if api_key:
            self.client = genai.Client(api_key="api_key")
        else:
            self.client = genai.Client()

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Google Generative AI.
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. (Currently not used by Gemini for task_type)
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")

        response = self.client.models.embed_content(
            model=self.config.model, content=text, output_dimensionality=self.config.embedding_dims
        )

        return response["embedding"]
