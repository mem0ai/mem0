import os
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings

try:
    from langchain_huggingface import HuggingFaceEndpointEmbeddings
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "The required dependencies for HuggingFaceHub are not installed."
        "Please install with `pip install langchain_huggingface`"
    ) from None

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.endpoint:
            if not self.config.api_key and "HUGGINGFACE_ACCESS_TOKEN" not in os.environ:
                raise ValueError(
                    "Please set the HUGGINGFACE_ACCESS_TOKEN environment variable or pass API Key in the config."
                )

            embeddings = HuggingFaceEndpointEmbeddings(
                model=self.config.endpoint,
                huggingfacehub_api_token=self.config.api_key or os.getenv("HUGGINGFACE_ACCESS_TOKEN"),
            )
        else:
            embeddings = HuggingFaceEmbeddings(model_name=self.config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.HUGGING_FACE.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
