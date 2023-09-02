from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.BaseEmbedder import BaseEmbedder
from langchain.embeddings import HuggingFaceEmbeddings

from typing import Optional

class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig]  = None):
        embeddings = HuggingFaceEmbeddings(model_name=config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        super().__init__(embedding_fn=embedding_fn)