from typing import Optional

from langchain_google_vertexai import VertexAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class VertexAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        kwargs = {}
        if getattr(config, "max_batch_size", None) is not None:
            kwargs["max_batch_size"] = config.max_batch_size
        embeddings = VertexAIEmbeddings(model_name=config.model, **kwargs)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.VERTEX_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
