import os
from typing import Literal, Optional

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

SCOPE = "https://cognitiveservices.azure.com/.default"


class AzureOpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        api_key = self.config.azure_kwargs.api_key or os.getenv("EMBEDDING_AZURE_OPENAI_API_KEY")
        azure_deployment = self.config.azure_kwargs.azure_deployment or os.getenv("EMBEDDING_AZURE_DEPLOYMENT")
        azure_endpoint = self.config.azure_kwargs.azure_endpoint or os.getenv("EMBEDDING_AZURE_ENDPOINT")
        api_version = self.config.azure_kwargs.api_version or os.getenv("EMBEDDING_AZURE_API_VERSION")
        default_headers = self.config.azure_kwargs.default_headers

        # If the API key is not provided or is a placeholder, use DefaultAzureCredential.
        if api_key is None or api_key == "" or api_key == "your-api-key":
            self.credential = DefaultAzureCredential()
            azure_ad_token_provider = get_bearer_token_provider(
                self.credential,
                SCOPE,
            )
            api_key = None
        else:
            azure_ad_token_provider = None

        self.client = AzureOpenAI(
            azure_deployment=azure_deployment,
            azure_endpoint=azure_endpoint,
            azure_ad_token_provider=azure_ad_token_provider,
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

    def embed_batch(self, texts, memory_action="add"):
        """Embed multiple texts in a single Azure OpenAI API call.

        Automatically chunks into batches of 100 to stay within API limits.
        """
        MAX_BATCH = 100
        texts = [text.replace("\n", " ") for text in texts]
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            response = self.client.embeddings.create(
                input=chunk,
                model=self.config.model,
            )
            all_embeddings.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
        return all_embeddings
