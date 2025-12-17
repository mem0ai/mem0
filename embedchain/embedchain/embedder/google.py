from typing import Optional, Union

from google import genai
from google.genai import types
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
        model = self.config.model or "gemini-embedding-001"
        title = self.config.title
        task_type = self.config.task_type
        if isinstance(input, str):
            input_ = [input]
        else:
            input_ = input
        
        result = self.client.models.embed_content(
            model=model, 
            contents=input_,
            config=types.EmbedContentConfig(task_type=task_type, title=title ,output_dimensionality=self.config.vector_dimension)
        )
            
        embeddings = result.embeddings
        if isinstance(input_, str):
            embeddings = [embeddings]
        return embeddings


class GoogleAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[GoogleAIEmbedderConfig] = None):
        super().__init__(config)
        embedding_fn = GoogleAIEmbeddingFunction(config=config)
        self.set_embedding_fn(embedding_fn=embedding_fn)

        vector_dimension = self.config.vector_dimension or VectorDimensions.GOOGLE_AI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
