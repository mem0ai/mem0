import os
from typing import Optional, Union

from chromadb import EmbeddingFunction, Embeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class MistralAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, config: BaseEmbedderConfig) -> None:
        super().__init__()
        try:
            from mistralai.client import MistralClient
        except ModuleNotFoundError:
            raise ModuleNotFoundError(
                "The required dependencies for MistralAI are not installed."
                'Please install with `pip install --upgrade "embedchain[mistralai]"`'
            ) from None
        self.config = config
        api_key = self.config.api_key or os.environ["MISTRAL_API_KEY"]
        self.client = MistralClient(api_key=api_key)

    def __call__(self, input: Union[list[str], str]) -> Embeddings:
        model = self.config.model
        if isinstance(input, str):
            input_ = [input]
        else:
            input_ = input
        response = self.client.embeddings(model=model, input=input_)
        return list(map(lambda x: x.embedding, response.data))


class MistralAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)

        if self.config.model is None:
            self.config.model = "mistral-embed"

        embedding_fn = MistralAIEmbeddingFunction(config=config)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.MISTRAL_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
