from typing import Optional, Literal

from mem0.embeddings.base import EmbeddingBase
from mem0.configs.embeddings.base import BaseEmbedderConfig

try:
    from fastembed import TextEmbedding
except ImportError:
    raise ImportError("FastEmbed is not installed.  Please install it using `pip install fastembed`")

class FastEmbedEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "thenlper/gte-large"
        self.dense_model = TextEmbedding(model_name=self.config.model)

        if not self.config.embedding_dims:
            self.config.embedding_dims = self.dense_model.embedding_size

    def embed_batch(self, texts, memory_action="add"):
        if not texts:
            return []
        embeddings = list(self.dense_model.embed(texts))
        if len(embeddings) != len(texts):
            raise ValueError(
                f"FastEmbed embed_batch() returned {len(embeddings)} embeddings for {len(texts)} texts"
                f" using model '{self.config.model}'"
            )
        return embeddings

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Convert the text to embeddings using FastEmbed running in the Onnx runtime
        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        embeddings = list(self.dense_model.embed(text))
        return embeddings[0]
