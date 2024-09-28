import os
from typing import Optional
import google.generativeai as genai

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class GoogleGenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        if self.config.model is None:
            self.config.model = "models/text-embedding-004" # embedding-dim = 768

        genai.configure(api_key=self.config.api_key or os.getenv("GOOGLE_API_KEY"))

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
        return response['embedding']