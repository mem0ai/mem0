from typing import Optional

from sentence_transformers import SentenceTransformer

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class HuggingFaceEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "multi-qa-MiniLM-L6-cos-v1"

        self.model = SentenceTransformer(self.config.model, **self.config.model_kwargs)

        self.config.embedding_dims = self.config.embedding_dims or self.model.get_sentence_embedding_dimension()

    def embed(self, text):
        """
        Get the embedding for the given text using Hugging Face.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        return self.model.encode(text, convert_to_numpy=True).tolist()
