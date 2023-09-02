from typing import Optional

from langchain.embeddings import VertexAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from embedchain.models import EmbeddingFunctions


class VertexAiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        embeddings = VertexAIEmbeddings(model_name=config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)

        vector_dimension = EmbeddingFunctions.GPT4ALL.value

        super().__init__(embedding_fn=embedding_fn, vector_dimension=vector_dimension)
