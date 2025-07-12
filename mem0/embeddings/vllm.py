import os
from typing import Literal, Optional

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class VllmEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        # Default embedding model
        self.config.model = self.config.model or "intfloat/e5-mistral-7b-instruct"
        self.config.embedding_dims = self.config.embedding_dims or 4096

        api_key = self.config.api_key or os.getenv("VLLM_API_KEY") or "vllm-api-key"
        base_url = (
            self.config.vllm_base_url 
            or os.getenv("VLLM_BASE_URL") 
            or "http://localhost:8000/v1"
        )

        self.client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using vLLM.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        
        response = self.client.embeddings.create(
            input=[text], 
            model=self.config.model
        )
        
        return response.data[0].embedding
