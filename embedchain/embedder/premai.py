import os 
import importlib
from typing import Optional 

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions

from langchain_community.embeddings.premai import PremAIEmbeddings

class PremAIEmbedder(BaseEmbedder):
    def __init__(self, project_id: int, config: Optional[BaseEmbedderConfig] = None) -> None:
        self.project_id = project_id
        super().__init__(config=config)

        try:
            importlib.import_module("premai")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for PremAI are not installed."
                'Please install with `pip install --upgrade "embedchain[premai]"`'
            ) from None
        
        _api_key = config.api_key or os.getenv("PREMAI_API_KEY")
        if _api_key is None:
            raise ValueError(
                "Please set PREMAI_API_KEY environment variable or pass in the config."
            )
        
        embeddings = PremAIEmbeddings(project_id=project_id, premai_api_key=_api_key)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimensions = self.config.vector_dimension or VectorDimensions.OPENAI
        self.set_vector_dimension(vector_dimension=vector_dimensions)
        