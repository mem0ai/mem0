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

    def embed_batch(self, texts, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Embed multiple texts in a single FastEmbed call.

        fastembed's ``TextEmbedding.embed()`` accepts an iterable of strings
        natively, so the whole batch is embedded in one pass instead of one
        ``embed()`` call per text (the base-class fallback).

        Args:
            texts (list[str]): The texts to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: A list of embedding vectors, one per input text.
        """
        if not texts:
            return []
        cleaned = [text.replace("\n", " ") for text in texts]
        embeddings = list(self.dense_model.embed(cleaned))
        if len(embeddings) != len(cleaned):
            raise ValueError(
                f"FastEmbed embed() returned {len(embeddings)} embeddings "
                f"for {len(cleaned)} texts using model '{self.config.model}'"
            )
        return [emb.tolist() for emb in embeddings]
