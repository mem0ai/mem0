import os
import warnings
from typing import Literal, Optional

from openai import AsyncOpenAI, OpenAI

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class OpenAIEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "text-embedding-3-small"
        # Only pass `dimensions` to the API when the user set embedding_dims; non-matryoshka
        # OpenAI-compatible backends (vLLM, Voyage, etc.) reject the parameter
        self._pass_dimensions_to_api = self.config.embedding_dims is not None
        self.config.embedding_dims = self.config.embedding_dims or 1536

        api_key = self.config.api_key or os.getenv("OPENAI_API_KEY")
        base_url = (
            self.config.openai_base_url
            or os.getenv("OPENAI_API_BASE")
            or os.getenv("OPENAI_BASE_URL")
            or "https://api.openai.com/v1"
        )
        if os.environ.get("OPENAI_API_BASE"):
            warnings.warn(
                "The environment variable 'OPENAI_API_BASE' is deprecated and will be removed in the 0.1.80. "
                "Please use 'OPENAI_BASE_URL' instead.",
                DeprecationWarning,
            )

        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.async_client = AsyncOpenAI(api_key=api_key, base_url=base_url)

    def _build_embedding_kwargs(self, texts):
        kwargs = {
            "input": texts,
            "model": self.config.model,
            "encoding_format": "float",
        }
        if self._pass_dimensions_to_api:
            kwargs["dimensions"] = self.config.embedding_dims
        return kwargs

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
        return self.client.embeddings.create(**self._build_embedding_kwargs([text])).data[0].embedding

    async def aembed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        text = text.replace("\n", " ")
        response = await self.async_client.embeddings.create(**self._build_embedding_kwargs([text]))
        return response.data[0].embedding

    def embed_batch(self, texts, memory_action="add"):
        """Embed multiple texts in a single OpenAI API call.

        Automatically chunks into batches of 100 to stay within API limits.
        """
        MAX_BATCH = 100
        texts = [text.replace("\n", " ") for text in texts]
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            response = self.client.embeddings.create(**self._build_embedding_kwargs(chunk))
            all_embeddings.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
        if len(all_embeddings) != len(texts):
            raise ValueError(
                f"OpenAI embed_batch() returned {len(all_embeddings)} embeddings for {len(texts)} texts"
                f" using model '{self.config.model}'"
            )
        return all_embeddings

    async def aembed_batch(self, texts, memory_action="add"):
        """Embed multiple texts in a single OpenAI API call.

        Automatically chunks into batches of 100 to stay within API limits.
        """
        MAX_BATCH = 100
        texts = [text.replace("\n", " ") for text in texts]
        all_embeddings = []
        for i in range(0, len(texts), MAX_BATCH):
            chunk = texts[i : i + MAX_BATCH]
            response = await self.async_client.embeddings.create(**self._build_embedding_kwargs(chunk))
            all_embeddings.extend(item.embedding for item in sorted(response.data, key=lambda x: x.index))
        if len(all_embeddings) != len(texts):
            raise ValueError(
                f"OpenAI embed_batch() returned {len(all_embeddings)} embeddings for {len(texts)} texts"
                f" using model '{self.config.model}'"
            )
        return all_embeddings
