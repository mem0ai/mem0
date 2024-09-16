import os
from typing import Optional

from vertexai.language_models import TextEmbeddingModel

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class VertexAI(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "text-embedding-004"
        self.config.embedding_dims = self.config.embedding_dims or 256

        credentials_path = self.config.vertex_credentials_json

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path
        elif not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            raise ValueError(
                "Google application credentials JSON is not provided. Please provide a valid JSON path or set the 'GOOGLE_APPLICATION_CREDENTIALS' environment variable."
            )

        self.model = TextEmbeddingModel.from_pretrained(self.config.model)

    def embed(self, text):
        """
        Get the embedding for the given text using Vertex AI.

        Args:
            text (str): The text to embed.

        Returns:
            list: The embedding vector.
        """
        embeddings = self.model.get_embeddings(texts=[text], output_dimensionality=self.config.embedding_dims)

        return embeddings[0].values
