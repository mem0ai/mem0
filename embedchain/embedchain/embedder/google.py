from typing import Optional, Union

from google import genai
from chromadb import EmbeddingFunction, Embeddings

from embedchain.config.embedder.google import GoogleAIEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class GoogleAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, config: Optional[GoogleAIEmbedderConfig] = None) -> None:
        super().__init__()
        self.config = config or GoogleAIEmbedderConfig()
        self.client = genai.Client()

    def __call__(self, input: Union[list[str], str]) -> Embeddings:
        response = self.client.models.embed_content(
            model=self.config.model,
            contents=input,
            config=genai.types.EmbedContentConfig(
                task_type=self.config.task_type,
                output_dimensionality=self.config.vector_dimension,
                title=self.config.title,
            ),
        )
        return [embedding.values for embedding in response.embeddings]


class GoogleAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[GoogleAIEmbedderConfig] = None):
        super().__init__(config)
        embedding_fn = GoogleAIEmbeddingFunction(config=config)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.GOOGLE_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
