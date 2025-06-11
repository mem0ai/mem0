from typing import Optional, Union

import google.generativeai as genai
from chromadb import EmbeddingFunction, Embeddings

from embedchain.config.embedder.google import GoogleAIEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class GoogleAIEmbeddingFunction(EmbeddingFunction):
    def __init__(self, config: Optional[GoogleAIEmbedderConfig] = None) -> None:
        super().__init__()
        self.config = config or GoogleAIEmbedderConfig()

    def __call__(self, input: Union[list[str], str]) -> Embeddings:
        model = self.config.model
        title = self.config.title
        task_type = self.config.task_type
        if isinstance(input, str):
            input_ = [input]
        else:
            input_ = input
        data = genai.embed_content(model=model, content=input_, task_type=task_type, title=title)
        embeddings = data["embedding"]
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
