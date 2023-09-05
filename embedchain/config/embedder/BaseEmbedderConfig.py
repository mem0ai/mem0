from typing import Optional

from embedchain.helper_classes.json_serializable import register_deserializable


@register_deserializable
class BaseEmbedderConfig:
    def __init__(self, model: Optional[str] = None, deployment_name: Optional[str] = None):
        self.model = model
        self.deployment_name = deployment_name
