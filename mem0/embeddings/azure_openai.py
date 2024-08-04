from typing import Optional
from openai import AzureOpenAI
import os
from mem0.embeddings.base import EmbeddingBase
from mem0.configs.embeddings.base import BaseEmbedderConfig

class AzureOpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if not self.config.model:
            self.config.model="text-embedding-ada-002"
        if not self.config.embedding_dims:
            self.config.embedding_dims=1536

        self.api_key=None
        self.azure_endpoint=None
        self.api_version = None
        
        if os.getenv("EMBED_AZURE_OPENAI_API_KEY") and os.getenv("EMBED_AZURE_OPENAI_ENDPOINT") and os.getenv("EMBED_OPENAI_API_VERSION"):
            
            self.api_key = os.getenv("EMBED_AZURE_OPENAI_API_KEY")
            self.azure_endpoint = os.getenv("EMBED_AZURE_OPENAI_ENDPOINT")
            self.api_version = os.getenv("EMBED_OPENAI_API_VERSION")
        else:
            self.api_key = os.getenv("AZURE_OPENAI_API_KEY")
            self.azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            self.api_version = os.getenv("AZURE_OPENAI_ENDPOINT")
        print(self.api_key, self.azure_endpoint, self.api_version)
        self.client = AzureOpenAI(api_version=self.api_version, api_key=self.api_key, azure_endpoint=self.azure_endpoint)

    def embed(self, text):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")

        return (
            self.client.embeddings.create(input=[text], model=self.config.model)
            .data[0]
            .embedding
        )