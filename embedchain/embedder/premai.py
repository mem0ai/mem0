import importlib
import os
from typing import Optional

from langchain_community.embeddings.premai import PremAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class PremAIConfig(BaseEmbedderConfig):
    def __init__(self, project_id: int, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.project_id = project_id


# TODO: create a similar function like MistralAI Embedding function


class PremAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[PremAIConfig] = None) -> None:
        super().__init__(config=config)

        try:
            importlib.import_module("premai")
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for PremAI are not installed."
                'Please install with `pip install --upgrade "embedchain[premai]"`'
            ) from None

        _api_key = self.config.api_key or os.getenv("PREMAI_API_KEY")
        if _api_key is None:
            raise ValueError("Please set PREMAI_API_KEY environment variable or pass in the config.")
        os.environ["PREMAI_API_KEY"] = _api_key

        embeddings = PremAIEmbeddings(project_id=config.project_id, model=config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimensions = self.config.vector_dimension or VectorDimensions.OPENAI
        self.set_vector_dimension(vector_dimension=vector_dimensions)
