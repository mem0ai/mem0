from typing import Optional

try:
    from langchain_aws import BedrockEmbeddings
except ModuleNotFoundError:
    raise ModuleNotFoundError(
        "The required dependencies for AWSBedrock are not installed." "Please install with `pip install langchain_aws`"
    ) from None

from embedchain.config.embedder.aws_bedrock import AWSBedrockEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class AWSBedrockEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[AWSBedrockEmbedderConfig] = None):
        super().__init__(config)

        if self.config.model is None or self.config.model == "amazon.titan-embed-text-v2:0":
            self.config.model = "amazon.titan-embed-text-v2:0"  # Default model if not specified
            vector_dimension = self.config.vector_dimension or VectorDimensions.AMAZON_TITAN_V2.value
        elif self.config.model == "amazon.titan-embed-text-v1":
            vector_dimension = VectorDimensions.AMAZON_TITAN_V1.value
        else:
            vector_dimension = self.config.vector_dimension

        embeddings = BedrockEmbeddings(model_id=self.config.model, model_kwargs=self.config.model_kwargs)
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)

        self.set_embedding_fn(embedding_fn=embedding_fn)
        self.set_vector_dimension(vector_dimension=vector_dimension)
