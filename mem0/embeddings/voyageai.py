import os
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    import voyageai
except ImportError:
    raise ImportError("VoyageAI is not installed. Please install it using `pip install voyageai`")


class VoyageAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "voyage-3"
        self.embedding_types = {
            "add": self.config.memory_add_embedding_type or "document",
            "update": self.config.memory_update_embedding_type or "document",
            "search": self.config.memory_search_embedding_type or "query",
        }

        api_key = self.config.api_key or os.getenv("VOYAGEAI_API_KEY")
        self.client = voyageai.Client(api_key=api_key)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using VoyageAI.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        input_type = self.embedding_types.get(memory_action) if memory_action else None
        kwargs = {"model": self.config.model, "input_type": input_type}
        if self.config.embedding_dims:
            kwargs["output_dimension"] = self.config.embedding_dims
        response = self.client.embed([text], **kwargs)
        return response.embeddings[0]

    def embed_batch(self, texts, memory_action="add"):
        """Embed multiple texts in a single VoyageAI API call."""
        input_type = self.embedding_types.get(memory_action) if memory_action else None
        kwargs = {"model": self.config.model, "input_type": input_type}
        if self.config.embedding_dims:
            kwargs["output_dimension"] = self.config.embedding_dims
        response = self.client.embed(list(texts), **kwargs)
        return response.embeddings
