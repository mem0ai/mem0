import os
from typing import Optional

from langchain.embeddings import OpenAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        kwargs = {}
        if self.config.model is None:
            self.config.model = "text-embedding-ada-002"

        kwargs["model"] = self.config.model
        if self.config.deployment_name:
            kwargs["deployment"] = self.config.deployment_name
        if os.getenv("OPENAI_API_KEY"):
            kwargs["openai_api_key"] = os.getenv("OPENAI_API_KEY")
        if os.getenv("OPENAI_ORGANIZATION"):
            kwargs["openai_organization"] = os.getenv("OPENAI_ORGANIZATION")

        embeddings = OpenAIEmbeddings(**kwargs)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)
        self.set_vector_dimension(vector_dimension=VectorDimensions.OPENAI.value)
