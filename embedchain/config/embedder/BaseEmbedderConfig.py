from typing import Optional


class BaseEmbedderConfig:
    def __init__(self, model: Optional[str] = None, deployment_name: Optional[str] = None):
        self.model = model
        self.deployment_name = deployment_name
