from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        embeddings = HuggingFaceEmbeddings(model_name=self.config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.HUGGING_FACE.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
