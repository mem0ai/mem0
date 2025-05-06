import subprocess
import sys
import os
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

try:
    from mistralai import Mistral
except ImportError:
    user_input = input("The 'mistralai' library is required. Install it now? [y/N]: ")
    if user_input.lower() == "y":
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "mistralai"])
            from mistralai import Mistral
        except subprocess.CalledProcessError:
            print("Failed to install 'mistralai'. Please install it manually using 'pip install mistralai'.")
            sys.exit(1)
    else:
        print("The required 'mistralai' library is not installed.")
        sys.exit(1)


class MistralAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "mistral-embed"

        api_key = self.config.api_key or os.getenv("MISTRAL_API_KEY")
        base_url = (
            self.config.mistralai_server_url
            or os.getenv("MISTRAL_SERVER_URL")
            or "https://api.mistral.ai"
        )

        self.client = Mistral(api_key=api_key, base_url=base_url)

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using MistralAI.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0]
            .embedding
        )
