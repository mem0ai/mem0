from abc import ABC
from typing import Dict, Optional, Union

import httpx

from mem0.configs.base import AzureConfig


class BaseEmbedderConfig(ABC):
    """
    Config for Embeddings.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        # Ollama specific
        ollama_base_url: Optional[str] = None,
        # Openai specific
        openai_base_url: Optional[str] = None,
        # Huggingface specific
        model_kwargs: Optional[dict] = None,
        # AzureOpenAI specific
        azure_kwargs: Optional[AzureConfig] = {},
        http_client_proxies: Optional[Union[Dict, str]] = None,
        # VertexAI specific
        vertex_credentials_json: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for the Embeddings.

        :param model: Embedding model to use, defaults to None
        :type model: Optional[str], optional
        :param api_key: API key to be use, defaults to None
        :type api_key: Optional[str], optional
        :param embedding_dims: The number of dimensions in the embedding, defaults to None
        :type embedding_dims: Optional[int], optional
        :param ollama_base_url: Base URL for the Ollama API, defaults to None
        :type ollama_base_url: Optional[str], optional
        :param model_kwargs: key-value arguments for the huggingface embedding model, defaults a dict inside init
        :type model_kwargs: Optional[Dict[str, Any]], defaults a dict inside init
        :param openai_base_url: Openai base URL to be use, defaults to "https://api.openai.com/v1"
        :type openai_base_url: Optional[str], optional
        :param azure_kwargs: key-value arguments for the AzureOpenAI embedding model, defaults a dict inside init
        :type azure_kwargs: Optional[Dict[str, Any]], defaults a dict inside init
        :param http_client_proxies: The proxy server settings used to create self.http_client, defaults to None
        :type http_client_proxies: Optional[Dict | str], optional
        """

        self.model = model
        self.api_key = api_key
        self.openai_base_url = openai_base_url
        self.embedding_dims = embedding_dims

        # AzureOpenAI specific
        self.http_client = httpx.Client(proxies=http_client_proxies) if http_client_proxies else None

        # Ollama specific
        self.ollama_base_url = ollama_base_url

        # Huggingface specific
        self.model_kwargs = model_kwargs or {}

        # AzureOpenAI specific
        self.azure_kwargs = AzureConfig(**azure_kwargs) or {}

        # VertexAI specific
        self.vertex_credentials_json = vertex_credentials_json
