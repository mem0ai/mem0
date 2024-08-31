import os
from typing import Optional

from openai import AzureOpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class AzureOpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        api_key = os.getenv("EMBEDDING_AZURE_OPENAI_API_KEY") or self.config.azure_kwargs.api_key
        azure_deployment = os.getenv("EMBEDDING_AZURE_DEPLOYMENT") or self.config.azure_kwargs.azure_deployment
        azure_endpoint = os.getenv("EMBEDDING_AZURE_ENDPOINT") or self.config.azure_kwargs.azure_endpoint
        api_version = os.getenv("EMBEDDING_AZURE_API_VERSION") or self.config.azure_kwargs.api_version
        
        self.client = AzureOpenAI(
            azure_deployment=azure_deployment, 
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client
            )

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
