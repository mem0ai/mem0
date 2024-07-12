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
        embedding_fn = BaseEmbedder._langchain_default_concept(
            BedrockEmbeddings(model_id=config.model, model_kwargs=self.config.model_kwargs)
        )
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.AWS_BEDROCK.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
