from typing import Optional

from langchain_aws import BedrockEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class AWSBedrockEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "amazon.titan-embed-text-v2:0"

        embeddings = BedrockEmbeddings(model_id=config.model, model_kwargs=self.config.model_kwargs)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)

        self.set_embedding_fn(embedding_fn=embedding_fn)
        vector_dimension = self.config.vector_dimension or VectorDimensions.AMAZON_TITAN_V2.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
