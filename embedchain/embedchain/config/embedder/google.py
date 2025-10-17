from typing import Optional

from embedchain.config.embedder.base import BaseEmbedderConfig
from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class GoogleAIEmbedderConfig(BaseEmbedderConfig):
    def __init__(
        self,
        model: Optional[str] = None,
        deployment_name: Optional[str] = None,
        vector_dimension: Optional[int] = None,
        task_type: Optional[str] = None,
        title: Optional[str] = None,
    ):
        super().__init__(model or "gemini-embedding-001", deployment_name, vector_dimension)
        self.task_type = task_type
        self.title = title
