import os
from typing import Literal, Optional

from google import genai
from google.genai import types

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "models/text-embedding-004"
        self.config.embedding_dims = self.config.embedding_dims or self.config.output_dimensionality or 768

        api_key = self.config.api_key or os.getenv("GOOGLE_API_KEY")

        self.client = genai.Client(api_key=api_key)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Google Generative AI.
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")

        # Create config for embedding parameters
        config = types.EmbedContentConfig(output_dimensionality=self.config.embedding_dims)

        # Call the embed_content method with the correct parameters
        response = self.client.models.embed_content(model=self.config.model, contents=text, config=config)

        return response.embeddings[0].values