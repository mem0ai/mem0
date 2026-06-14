from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

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
        return embeddings[0].tolist()

    def embed_batch(self, texts, memory_action="add"):
        """
        Embed multiple texts in a single FastEmbed call.
        """
        texts = [text.replace("\n", " ") for text in texts]
        return [emb.tolist() for emb in self.dense_model.embed(texts)]
