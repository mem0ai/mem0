from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from langchain.embeddings import HuggingFaceEmbeddings
from chromadb.utils import embedding_functions

from typing import Optional

class GPT4AllEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig]  = None):
        # Note: We could use langchains GPT4ALL embedding, but it's not available in all versions.
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=config.model)
        super().__init__(embedding_fn=embedding_fn)