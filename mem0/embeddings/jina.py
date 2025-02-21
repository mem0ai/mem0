import os
from typing import Optional

import requests

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class JinaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "jina-embeddings-v3"
        self.config.embedding_dims = self.config.embedding_dims or 768

        api_key = self.config.api_key or os.getenv("JINA_API_KEY")
        if not api_key:
            raise ValueError("Jina API key is required. Set it in config or JINA_API_KEY environment variable.")
        
        base_url = self.config.jina_base_url or os.getenv("JINA_API_BASE", "https://api.jina.ai")
        
        self.base_url = f"{base_url}/v1/embeddings"
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

    def embed(self, text):
        """
        Get the embedding for the given text using Jina AI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        
        data = {
            "model": self.config.model,
            "input": [{"text": text}]
        }

        if self.config.model_kwargs:
            data.update(self.config.model_kwargs)

        response = requests.post(self.base_url, headers=self.headers, json=data)
        response.raise_for_status()
        
        return response.json()["data"][0]["embedding"] 