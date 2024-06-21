import os
from typing import Optional

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.embeddings.huggingface import HuggingFaceInferenceAPIEmbeddings

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

            embeddings = HuggingFaceInferenceAPIEmbeddings(
                model_name=self.config.model,
                api_url=self.config.endpoint,
                api_key=self.config.api_key or os.getenv("HUGGINGFACE_ACCESS_TOKEN"),
            )
        else:
            embeddings = HuggingFaceEmbeddings(model_name=self.config.model)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.HUGGING_FACE.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
