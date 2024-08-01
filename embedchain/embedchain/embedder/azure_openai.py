from typing import Optional

from langchain_openai import AzureOpenAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class AzureOpenAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "text-embedding-ada-002"

        embeddings = AzureOpenAIEmbeddings(
            deployment=self.config.deployment_name,
            http_client=self.config.http_client,
            http_async_client=self.config.http_async_client,
        )
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)

        self.set_embedding_fn(embedding_fn=embedding_fn)
        vector_dimension = self.config.vector_dimension or VectorDimensions.OPENAI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
