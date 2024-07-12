import ollama
from embedding.base import EmbeddingBase


class OllamaEmbedding(EmbeddingBase):
    def __init__(self, model="nomic-embed-text"):
        self.model = model
        self._ensure_model_exists()
        self.dims = 512

    def _ensure_model_exists(self):
        """
        Ensure the specified model exists locally. If not, pull it from Ollama.
        """
        model_list = [m["name"] for m in ollama.list()["models"]]
        if not any(m.startswith(self.model) for m in model_list):
            ollama.pull(self.model)

    def embed(self, text):
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        response = ollama.embeddings(model=self.model, prompt=text)
        return response["embedding"]
