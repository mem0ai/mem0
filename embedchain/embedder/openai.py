import os
from typing import Optional

from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from langchain.embeddings import AzureOpenAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "text-embedding-ada-002"

        if self.config.deployment_name:
            embeddings = AzureOpenAIEmbeddings(deployment=self.config.deployment_name)
            embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        else:
            if os.getenv("OPENAI_API_KEY") is None and os.getenv("OPENAI_ORGANIZATION") is None:
                raise ValueError(
                    "OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided"
                )  # noqa:E501
            embedding_fn = OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name=self.config.model,
            )
        self.set_embedding_fn(embedding_fn=embedding_fn)
        self.set_vector_dimension(vector_dimension=VectorDimensions.OPENAI.value)
