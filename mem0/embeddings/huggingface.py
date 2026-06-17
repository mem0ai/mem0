import logging
from typing import Literal, Optional

from openai import OpenAI
from sentence_transformers import SentenceTransformer

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

logging.getLogger("transformers").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)


class HuggingFaceEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if self.config.huggingface_base_url:
            self.client = OpenAI(base_url=self.config.huggingface_base_url)
            self.config.model = self.config.model or "tei"
        else:
            self.config.model = self.config.model or "multi-qa-MiniLM-L6-cos-v1"

            self.model = SentenceTransformer(self.config.model, **self.config.model_kwargs)

            self.config.embedding_dims = self.config.embedding_dims or self.model.get_sentence_embedding_dimension()

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Hugging Face.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        if self.config.huggingface_base_url:
            return self.client.embeddings.create(
                input=text, model=self.config.model, **self.config.model_kwargs
            ).data[0].embedding
        else:
            return self.model.encode(text, convert_to_numpy=True).tolist()

    def embed_batch(self, texts, memory_action="add"):
        if not texts:
            return []
        if self.config.huggingface_base_url:
            response = self.client.embeddings.create(input=texts, model=self.config.model, **self.config.model_kwargs)
            sorted_data = sorted(response.data, key=lambda x: x.index)
            embeddings = [item.embedding for item in sorted_data]
            if len(embeddings) != len(texts):
                raise ValueError(
                    f"HuggingFace embed() returned {len(embeddings)} embeddings for {len(texts)} texts"
                    f" using model '{self.config.model}'"
                )
            return embeddings
        else:
            result = self.model.encode(texts, convert_to_numpy=True).tolist()
            if len(result) != len(texts):
                raise ValueError(
                    f"HuggingFace embed() returned {len(result)} embeddings for {len(texts)} texts"
                    f" using model '{self.config.model}'"
                )
            return result
