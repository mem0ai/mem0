import os
from typing import Literal, Optional

from openai import AzureOpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class AzureOpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        api_key = self.config.azure_kwargs.api_key or os.getenv("EMBEDDING_AZURE_OPENAI_API_KEY")
        azure_deployment = self.config.azure_kwargs.azure_deployment or os.getenv("EMBEDDING_AZURE_DEPLOYMENT")
        azure_endpoint = self.config.azure_kwargs.azure_endpoint or os.getenv("EMBEDDING_AZURE_ENDPOINT")
        api_version = self.config.azure_kwargs.api_version or os.getenv("EMBEDDING_AZURE_API_VERSION")
        default_headers = self.config.azure_kwargs.default_headers

        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            api_version=api_version,
            api_key=api_key,
            http_client=self.config.http_client,
            default_headers=default_headers,
        )

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using OpenAI.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        return self.client.embeddings.create(input=[text], model=self.config.model).data[0].embedding
