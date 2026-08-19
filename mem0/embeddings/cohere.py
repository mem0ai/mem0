import os
from typing import Literal, Optional

try:
    import cohere
except ImportError:
    raise ImportError("Cohere requires extra dependencies. Install with `pip install cohere`")

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class CohereEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "embed-english-v3.0"

        api_key = self.config.api_key or os.getenv("COHERE_API_KEY")

        self.client = cohere.Client(api_key=api_key)

    def _get_input_type(self, memory_action: Optional[str]) -> str:
        if memory_action == "add":
            return "search_document"
        elif memory_action == "search":
            return "search_query"
        elif memory_action == "update":
            return "search_document"
        return "search_document"

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Cohere.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        
        input_type = self._get_input_type(memory_action)

        response = self.client.embed(
            texts=[text],
            model=self.config.model,
            input_type=input_type,
        )
        return response.embeddings[0]

    def embed_batch(self, texts: list[str], memory_action: Optional[Literal["add", "search", "update"]] = "add"):
        """Embed multiple texts in a single Cohere API call.

        Automatically chunks into batches of 96 (Cohere's limit).
        """
        MAX_BATCH = 96
        texts = [text.replace("\n", " ") for text in texts]
        all_embeddings = []
        input_type = self._get_input_type(memory_action)

        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            response = self.client.embed(
                texts=chunk,
                model=self.config.model,
                input_type=input_type,
            )
            all_embeddings.extend(response.embeddings)
            
        if len(all_embeddings) != len(texts):
            raise ValueError(
                f"Cohere embed_batch() returned {len(all_embeddings)} embeddings for {len(texts)} texts"
                f" using model '{self.config.model}'"
            )
        return all_embeddings
