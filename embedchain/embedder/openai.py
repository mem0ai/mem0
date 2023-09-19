import os
from typing import Optional

from langchain.embeddings import OpenAIEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.models import VectorDimensions

try:
    from chromadb.utils import embedding_functions
except RuntimeError:
    from embedchain.utils import use_pysqlite3

    use_pysqlite3()
    from chromadb.utils import embedding_functions


@register_deserializable
class OpenAiEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)
        if self.config.model is None:
            self.config.model = "text-embedding-ada-002"

        self.set_embedding_fn(embedding_fn=self._get_embedding_fn())
        self.set_vector_dimension(vector_dimension=VectorDimensions.OPENAI.value)

    def _get_embedding_fn(self):
        if self.config.deployment_name:
            embeddings = OpenAIEmbeddings(deployment=self.config.deployment_name)
            embedding_fn = BaseEmbedder._langchain_default_concept(embeddings)
            return embedding_fn
        else:
            if os.getenv("OPENAI_API_KEY") is None and os.getenv("OPENAI_ORGANIZATION") is None:
                raise ValueError(
                    "OPENAI_API_KEY or OPENAI_ORGANIZATION environment variables not provided"
                )  # noqa:E501
            embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                organization_id=os.getenv("OPENAI_ORGANIZATION"),
                model_name=self.config.model,
            )
            return embedding_fn
