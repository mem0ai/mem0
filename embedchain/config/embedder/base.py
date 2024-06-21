from typing import Optional

from embedchain.helpers.json_serializable import register_deserializable


@register_deserializable
class BaseEmbedderConfig:
    def __init__(
        self,
        model: Optional[str] = None,
        deployment_name: Optional[str] = None,
        vector_dimension: Optional[int] = None,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """
        Initialize a new instance of an embedder config class.

        :param model: model name of the llm embedding model (not applicable to all providers), defaults to None
        :type model: Optional[str], optional
        :param deployment_name: deployment name for llm embedding model, defaults to None
        :type deployment_name: Optional[str], optional
        :param vector_dimension: vector dimension of the embedding model, defaults to None
        :type vector_dimension: Optional[int], optional
        :param endpoint: endpoint for the embedding model, defaults to None
        :type endpoint: Optional[str], optional
        :param api_key: hugginface api key, defaults to None
        :type api_key: Optional[str], optional
        :param api_base: huggingface api base, defaults to None
        :type api_base: Optional[str], optional
        """
        self.model = model
        self.deployment_name = deployment_name
        self.vector_dimension = vector_dimension
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_base = api_base
