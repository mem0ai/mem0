from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from langchain.embeddings import VertexAIEmbeddings

from typing import Optional

class VertexAiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig]  = None):
        embeddings = VertexAIEmbeddings(model_name=config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        super().__init__(embedding_fn=embedding_fn)