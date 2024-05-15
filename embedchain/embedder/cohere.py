from typing import Optional

from langchain_cohere.embeddings import CohereEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class CohereEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        embeddings = CohereEmbeddings(model=self.config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.COHERE.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
