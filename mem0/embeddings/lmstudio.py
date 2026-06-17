from typing import Literal, Optional

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class LMStudioEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
        self.config.embedding_dims = self.config.embedding_dims or 1536
        self.config.api_key = self.config.api_key or "lm-studio"

        self.client = OpenAI(base_url=self.config.lmstudio_base_url, api_key=self.config.api_key)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using LM Studio.
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return self.client.embeddings.create(input=[text], model=self.config.model).data[0].embedding

    def embed_batch(self, texts, memory_action="add"):
        """Embed multiple texts via LM Studio's OpenAI-compatible batch API.

        Chunks into batches of 100 to stay within typical server limits.
        """
        MAX_BATCH = 100
        texts = [text.replace("\n", " ") for text in texts]
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            response = self.client.embeddings.create(input=chunk, model=self.config.model)
            all_embeddings.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
        return all_embeddings
