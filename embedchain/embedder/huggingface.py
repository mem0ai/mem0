from typing import Optional

from langchain.embeddings import HuggingFaceEmbeddings

from embedchain.config import BaseEmbedderConfig
from embedchain.embedder.base import BaseEmbedder
from embedchain.helper.json_serializable import register_deserializable
from embedchain.models import VectorDimensions


@register_deserializable
class HuggingFaceEmbedder(BaseEmbedder):
    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config=config)

        self.set_embedding_fn(embedding_fn=self._get_embedding_fn())

        vector_dimension = VectorDimensions.HUGGING_FACE.value
        self.set_vector_dimension(vector_dimension=vector_dimension)

    def _get_embedding_fn(self):
        embeddings = HuggingFaceEmbeddings(model_name=self.config.model)
        return BaseEmbedder._langchain_default_concept(embeddings)