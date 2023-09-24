from typing import Optional

from chromadb.utils import embedding_functions

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class GPT4AllEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        # Note: We could use langchains GPT4ALL embedding, but it's not available in all versions.
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "all-MiniLM-L6-v2"

        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=self.config.model)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = VectorDimensions.GPT4ALL.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
