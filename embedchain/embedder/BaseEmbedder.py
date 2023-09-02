from typing import Any, Callable

try:
    from chromadb.api.types import Documents, Embeddings
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.api.types import Documents, Embeddings


class BaseEmbedder:
    """Class that manages everything regarding embeddings. Including embedding function, loaders and chunkers."""

    def __init__(self, embedding_fn: Callable[[list[str]], list[str]] = None, vector_dimensions: int = None):
        if not hasattr(embedding_fn, "__call__"):
            raise ValueError("Embedding function is not a function")
        self.embedding_fn = embedding_fn
        self.vector_dimensions = vector_dimensions

    @staticmethod
    def _langchain_default_concept(embeddings: Any):
        """
        Langchains default function layout for embeddings.
        """

        def embed_function(texts: Documents) -> Embeddings:
            return embeddings.embed_documents(texts)

        return embed_function
