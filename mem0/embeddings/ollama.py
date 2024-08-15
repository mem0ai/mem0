from typing import Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    from ollama import Client
except ImportError:
    raise ImportError(
        "Ollama requires extra dependencies. Install with `pip install ollama`"
    ) from None


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model = "nomic-embed-text"
        if not self.config.embedding_dims:
            self.config.embedding_dims = 512

        self.client = Client(host=self.config.ollama_base_url)
        self._ensure_model_exists()

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        local_models = self.client.list()["models"]
        if not any(model.get("name") == self.config.model for model in local_models):
            self.client.pull(self.config.model)

    def embed(self, text):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        response = self.client.embeddings(model=self.config.model, prompt=text)
        return response["embedding"]
