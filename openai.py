import os
from typing import List, Optional, Union
from openai import OpenAI
from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase
import asyncio

class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "text-embedding-3-small"
        self.config.embedding_dims = self.config.embedding_dims or 1536

        api_key = os.getenv("OPENAI_API_KEY") or self.config.api_key
        base_url = os.getenv("OPENAI_API_BASE") or self.config.openai_base_url
        self.client = OpenAI(api_key=api_key, base_url=base_url)

    async def embed(self, texts: Union[str, List[str]]) -> List[List[float]]:
        """
        Get embeddings for the given texts using OpenAI. Supports batch processing.

        Args:
            texts (Union[str, List[str]]): A single text or a list of texts to embed.

        Returns:
            List[List[float]]: The embedding vectors for the input texts.
        """
        if isinstance(texts, str):
            texts = [texts]
        
        texts = [text.replace("\n", " ") for text in texts]

        try:
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.client.embeddings.create(input=texts, model=self.config.model)
            )
            embeddings = [datum.embedding for datum in response.data]
            return embeddings

        except Exception as e:
            # Implement proper error handling
            print(f"Error during embedding: {e}")
            return []

# Example usage (for asynchronous context):
# embedding_instance = OpenAIEmbedding()
# embeddings = asyncio.run(embedding_instance.embed(["Example text 1", "Example text 2"]))
