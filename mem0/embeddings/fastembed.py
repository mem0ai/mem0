from embedding.base import EmbeddingBase

try:
    from fastembed import TextEmbedding
except ImportError as e:
    raise ImportError(
        "The 'fastembed' package is not installed. Please install it with `pip install fastembed`"
    ) from e


class FastEmbedEmbedding(EmbeddingBase):
    """
    Generate embeddings vector embeddings using FastEmbed - https://qdrant.github.io/fastembed/.
    Find the list of supported models at https://qdrant.github.io/fastembed/examples/Supported_Models/.
    """

    def __init__(
        self,
        model="BAAI/bge-small-en-v1.5",
    ) -> None:
        self.model = model
        self.dims = 384
        self._model = TextEmbedding(model_name=model)

    def embed(self, text):
        return next(self._model.embed(text)).tolist()
