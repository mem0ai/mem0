from typing import Optional

from chromadb.utils import embedding_functions

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from embedchain.models import EmbeddingFunctions


class GPT4AllEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        # Note: We could use langchains GPT4ALL embedding, but it's not available in all versions.
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.model)

        vector_dimensions = EmbeddingFunctions.GPT4ALL.value

        super().__init__(embedding_fn=embedding_fn, vector_dimensions=vector_dimensions)
