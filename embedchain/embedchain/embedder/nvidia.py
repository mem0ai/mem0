import logging
import os
from typing import Optional

from langchain_nvidia_ai_endpoints import NVIDIAEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions

logger = logging.getLogger(__name__)


class NvidiaEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        if "NVIDIA_API_KEY" not in os.environ:
            raise ValueError("NVIDIA_API_KEY environment variable must be set")

        super().__init__(config=config)

        model = self.config.model or "nvolveqa_40k"
        logger.info(f"Using NVIDIA embedding model: {model}")
        embedder = NVIDIAEmbeddings(model=model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embedder)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.NVIDIA_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
