from typing import Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase

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

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self._model = TextEmbedding(model_name=self.config.model, **self.config.model_kwargs)

    def embed(self, text):
        return next(self._model.embed(text)).tolist()
