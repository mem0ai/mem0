import logging
from typing import Optional

try:
    import ollama
except ImportError:
    raise ImportError("Ollama Embedder requires extra dependencies. Install with `pip install ollama`") from None

from langchain_community.embeddings import OllamaEmbeddings

from embedchain.config import OllamaEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions

logger = logging.getLogger(__name__)


class OllamaEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[OllamaEmbedderConfig] = None):
        super().__init__(config=config)

        local_models = ollama.list()["models"]
        if not any(model.get("name") == self.config.model for model in local_models):
            logger.info(f"Pulling {self.config.model} from Ollama!")
            ollama.pull(self.config.model)
        embeddings = OllamaEmbeddings(model=self.config.model, base_url=self.config.base_url)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.OLLAMA.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
