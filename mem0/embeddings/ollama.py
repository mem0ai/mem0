import subprocess
import sys
from typing import List, Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    from ollama import Client
except ImportError:
    user_input = input("The 'ollama' library is required. Install it now? [y/N]: ")
    if user_input.lower() == "y":
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ollama"])
            from ollama import Client
        except subprocess.CalledProcessError:
            print("Failed to install 'ollama'. Please install it manually using 'pip install ollama'.")
            sys.exit(1)
    else:
        print("The required 'ollama' library is not installed.")
        sys.exit(1)


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

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = "add") -> List[float]:
        """
        Get the embedding for the given text using Ollama.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to "add".
        Returns:
            List[float]: The embedding vector.
        """
        # Early exit if the text is empty or only whitespace
        if not text or not text.strip():
            raise ValueError("Cannot generate embedding for an empty or whitespace-only string.")

        response = self.client.embed(model=self.config.model, input=text)
        embeddings = response.get("embeddings") or []
        if not embeddings:
            raise ValueError(f"Ollama embed() returned no embeddings for model '{self.config.model}'")
        return embeddings[0]
    
    def embed_batch(self, texts: List[str], memory_action: Optional[Literal["add", "search", "update"]] = "add") -> List[List[float]]:
        """
        Get batch embeddings for multiple texts using Ollama's native batch support.

        Ollama's embed() accepts an array of strings for batch processing, reducing
        N sequential API calls to a single batched call.

        Args:
            texts (List[str]): List of texts to embed.
            memory_action (optional): The type of embedding to use. Defaults to "add".
        Returns:
            List[List[float]]: List of embedding vectors for each text.
        """
        if not texts:
            return []

        if len(texts) == 1:
            return [self.embed(texts[0], memory_action=memory_action)]

        response = self.client.embed(model=self.config.model, input=texts)
        embeddings = response.get("embeddings") or []
        
        if not embeddings:
            raise ValueError(f"Ollama embed() returned no embeddings for model '{self.config.model}'")
        
        return embeddings