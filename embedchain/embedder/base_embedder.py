from typing import Any, Callable, Optional

from embedchain.config.embedder.BaseEmbedderConfig import BaseEmbedderConfig

try:
    from chromadb.api.types import Documents, Embeddings
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.api.types import Documents, Embeddings


class BaseEmbedder:
    """
    Class that manages everything regarding embeddings. Including embedding function, loaders and chunkers.

    Embedding functions and vector dimensions are set based on the child class you choose.
    To manually overwrite you can use this classes `set_...` methods.
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = FileNotFoundError):
        if config is None:
            self.config = BaseEmbedderConfig()
        else:
            self.config = config
        self.vector_dimension: int

    def set_embedding_fn(self, embedding_fn: Callable[[list[str]], list[str]]):
        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")
        self.embedding_fn = embedding_fn

    def set_vector_dimension(self, vector_dimension: int):
        self.vector_dimension = vector_dimension

    @staticmethod
    def _langchain_default_concept(embeddings: Any):
        """
        Langchains default function layout for embeddings.
        """

        def embed_function(texts: Documents) -> Embeddings:
            return embeddings.embed_documents(texts)

        return embed_function
