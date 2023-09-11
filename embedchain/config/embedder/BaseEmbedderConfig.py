from typing import Optional

from embedchain.helper.json_serializable import register_deserializable


@register_deserializable
class BaseEmbedderConfig:
    def __init__(self, model: Optional[str] = None, deployment_name: Optional[str] = None):
        """
        Initialize a new instance of an embedder config class.

        :param model: model name of the llm embedding model (not applicable to all providers), defaults to None
        :type model: Optional[str], optional
        :param deployment_name: deployment name for llm embedding model, defaults to None
        :type deployment_name: Optional[str], optional
        """
        self.model = model
        self.deployment_name = deployment_name
