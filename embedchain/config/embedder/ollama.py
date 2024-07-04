from typing import Optional

from embedchain.config.embedder.base import BaseEmbedderConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class OllamaEmbedderConfig(BaseEmbedderConfig):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        vector_dimension: Optional[int] = None,
    ):
        super().__init__(model=model, vector_dimension=vector_dimension)
        self.base_url = base_url or "http://localhost:11434"
