import subprocess
import sys
from typing import Literal, Optional

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

    def _ensure_model_exists(self):
        """
         Ensure the specified model exists locally. If not, pull it from Ollama.
    
        BUG FIX (v0.1.115): Fixed model existence checking logic to properly handle
        Ollama's response format. The original code incorrectly used `model.get("name")`
        which always returned None, causing unnecessary model downloads even when
        models were already available locally.
        
        The fix changes the model checking logic from:
            `model.get("name") == self.config.model`
        to:
            `hasattr(model, 'model') and model.model == self.config.model`
        
        This correctly accesses the model name from Ollama's response objects,
        which have the model name stored in the `model` attribute, not as a
        dictionary key "name".
        
        Impact:
        - Prevents unnecessary model downloads when models already exist locally
        - Fixes timeout errors when trying to download already-available models
        - Improves performance by avoiding redundant network requests
        - Resolves compatibility issues with system-wide Ollama installations
        """
        local_models = self.client.list()["models"]
        if not any(hasattr(model, 'model') and model.model == self.config.model for model in local_models): 
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
        response = self.client.embeddings(model=self.config.model, prompt=text)
        return response["embedding"]
