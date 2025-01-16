from typing import List, Optional, Sequence, Union

try:
    from fastembed import TextEmbedding
except ImportError:
    raise ValueError("The 'fastembed' package is not installed. Please install it with `pip install fastembed`")

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions

Embedding = Sequence[float]
Embeddings = List[Embedding]


class FastEmbedEmbedder(BaseEmbedder):
    """
    Generate embeddings using FastEmbed - https://qdrant.github.io/fastembed/.
    Find the list of supported models at https://qdrant.github.io/fastembed/examples/Supported_Models/.
    """
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        self.config.model = self.config.model or "BAAI/bge-small-en-v1.5"

        embedding_fn = FastEmbedEmbeddingFunction(config=self.config)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.FASTEMBED.value
        self.set_vector_dimension(vector_dimension=vector_dimension)


class FastEmbedEmbeddingFunction:
    def __init__(self, config: BaseEmbedderConfig) -> None:
        self.config = config
        self._model = TextEmbedding(model_name=self.config.model, **self.config.model_kwargs)

    def __call__(self, input: Union[list[str], str]) -> List[Embedding]:
        embeddings = self._model.embed(input)
        return [embedding.tolist() for embedding in embeddings]
