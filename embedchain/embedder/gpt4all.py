from typing import Optional

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class GPT4AllEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        from langchain.embeddings import \
            GPT4AllEmbeddings as LangchainGPT4AllEmbeddings

        embeddings = LangchainGPT4AllEmbeddings()
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = VectorDimensions.GPT4ALL.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
