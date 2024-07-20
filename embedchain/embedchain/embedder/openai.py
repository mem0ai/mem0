import os
from typing import Optional

from langchain_openai import OpenAIEmbeddings


from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.models import VectorDimensions


class OpenAIEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        if self.config.model is None:
            self.config.model = "text-embedding-ada-002"

        api_key = self.config.api_key or os.environ["OPENAI_API_KEY"]
        api_base = self.config.api_base or os.environ.get("OPENAI_API_BASE")

        if api_key is None and os.getenv("OPENAI_ORGANIZATION") is None:
            raise ValueError("OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided")  # noqa:E501
        embeddings = OpenAIEmbeddings(
            api_key=api_key,
            base_url=api_base,
            organization=os.getenv("OPENAI_ORGANIZATION"),
            model=self.config.model,
        )
        embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
        self.set_embedding_fn(embedding_fn=embedding_fn)
        vector_dimension = self.config.vector_dimension or VectorDimensions.OPENAI.value
        self.set_vector_dimension(vector_dimension=vector_dimension)
