from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    from ollama import Client
except ImportError:
    raise ImportError("The 'ollama' library is required. Please install it using 'pip install ollama'.")


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "nomic-embed-text"
        self.config.embedding_dims = self.config.embedding_dims or 512

        self.client = Client(host=self.config.ollama_base_url)
        self._ensure_model_exists()

    @staticmethod
    def _normalize_model_name(name: str) -> str:
        return name if ":" in name else f"{name}:latest"

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        local_models = self.client.list()["models"]
        target = self._normalize_model_name(self.config.model)
        if not any(
            self._normalize_model_name(model.get("name", "")) == target
            or self._normalize_model_name(model.get("model", "")) == target
            for model in local_models
        ):
            self.client.pull(self.config.model)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        response = self.client.embed(model=self.config.model, input=text)
        embeddings = response.get("embeddings") or []
        if not embeddings:
            raise ValueError(f"Ollama embed() returned no embeddings for model '{self.config.model}'")
        return embeddings[0]

    def embed_batch(self, texts, memory_action="add"):
        """Embed multiple texts in a single Ollama API call."""
        if not texts:
            return []
        response = self.client.embed(model=self.config.model, input=texts)
        embeddings = response.get("embeddings") or []
        if len(embeddings) != len(texts):
            raise ValueError(f"Ollama embed() returned {len(embeddings)} embeddings for {len(texts)} texts using model '{self.config.model}'")
        return embeddings
