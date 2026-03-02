from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

# Support both LangChain v0.2+ and v1.0+
try:
    # Try LangChain v1.0+ import path first (langchain-core >= 0.3)
    from langchain_core.embeddings import Embeddings
except ImportError:
    try:
        # Fall back to LangChain v0.2+ import path
        from langchain.embeddings.base import Embeddings
    except ImportError:
        raise ImportError(
            "langchain is not installed. Please install it using "
            "`pip install langchain langchain-core`"
        )


class LangchainEmbedding(EmbeddingBase):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if self.config.model is None:
            raise ValueError("`model` parameter is required")

        if not isinstance(self.config.model, Embeddings):
            raise ValueError("`model` must be an instance of Embeddings")

        self.langchain_model = self.config.model

    def embed(self, text, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using Langchain.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Must be one of "add", "search", or "update". Defaults to None.
        Returns:
            list: The embedding vector.
        """

        return self.langchain_model.embed_query(text)
