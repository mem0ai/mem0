from typing import Any, Dict, Optional, Union

import httpx

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
        model_kwargs: Optional[Dict[str, Any]] = None,
        http_client_proxies: Optional[Union[Dict, str]] = None,
        http_async_client_proxies: Optional[Union[Dict, str]] = None,
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
        :param model_kwargs: key-value arguments for the embedding model, defaults a dict inside init.
        :type model_kwargs: Optional[Dict[str, Any]], defaults a dict inside init.
        :param http_client_proxies: The proxy server settings used to create self.http_client, defaults to None
        :type http_client_proxies: Optional[Dict | str], optional
        :param http_async_client_proxies: The proxy server settings for async calls used to create
        self.http_async_client, defaults to None
        :type http_async_client_proxies: Optional[Dict | str], optional
        """
        self.model = model
        self.deployment_name = deployment_name
        self.vector_dimension = vector_dimension
        self.endpoint = endpoint
        self.api_key = api_key
        self.api_base = api_base
        self.model_kwargs = model_kwargs or {}
        self.http_client = httpx.Client(proxies=http_client_proxies) if http_client_proxies else None
        self.http_async_client = (
            httpx.AsyncClient(proxies=http_async_client_proxies) if http_async_client_proxies else None
        )
