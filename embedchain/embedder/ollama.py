from typing import Optional

from langchain_community.embeddings import OllamaEmbeddings

from embedchain.config import OllamaEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[OllamaEmbedderConfig] = None):
        super().__init__(config=config)

        embeddings = OllamaEmbeddings(model=self.config.model, base_url=self.config.base_url)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.OLLAMA.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
