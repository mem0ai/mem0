import os
from typing import Optional

from langchain.embeddings import GooglePalmEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base_embedder import BaseEmbedder
from embedchain.models import EmbeddingFunctions


class PalmEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if os.getenv("GOOGLE_API_KEY") is None:
            raise ValueError("GOOGLE_API_KEY environment variables not provided")

        model = "models/embedding-gecko-001"
        if (config is not None) and (config.model is not None):
            model = config.model

        embeddings = GooglePalmEmbeddings(model_name=model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)

        self.set_embedding_fn(embedding_fn=embedding_fn)
        self.set_vector_dimension(vector_dimension=EmbeddingFunctions.PALM.value)
