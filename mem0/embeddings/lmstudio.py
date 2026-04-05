from typing import Literal, Optional

from openai import OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class LMStudioEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-ai/nomic-embed-text-v1.5-GGUF/nomic-embed-text-v1.5.f16.gguf"
        self.config.api_key = self.config.api_key or "lm-studio"

        self.client = OpenAI(base_url=self.config.lmstudio_base_url, api_key=self.config.api_key)

        if not self.config.embedding_dims:
            self.config.embedding_dims = self._detect_embedding_dims()

    def _detect_embedding_dims(self) -> int:
        """
        Auto-detect the embedding dimensions by making a test embed call.

        LM Studio can serve any locally loaded model, so the output dimensions
        depend entirely on which model the user has loaded. The previous hardcoded
        fallback of 1536 only matches OpenAI text-embedding-3-small/ada-002 and
        causes dimension mismatch errors with any other model (e.g. nomic-embed-text
        at 768, bge-large at 1024, etc.).
        """
        try:
            response = self.client.embeddings.create(input=["test"], model=self.config.model)
            return len(response.data[0].embedding)
        except Exception:
            return 1536

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
