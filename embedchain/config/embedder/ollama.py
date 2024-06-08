from typing import Optional

from embedchain.config.embedder.base import BaseEmbedderConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class OllamaEmbedderConfig(BaseEmbedderConfig):
    def __init__(
        self,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        super().__init__(model)
        self.base_url = base_url or "http://localhost:11434"
