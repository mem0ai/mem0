import os
from abc import ABC
from typing import Dict, Optional, Union

import httpx

from mem0.configs.base import AzureConfig


def _build_http_client(http_client_proxies: Optional[Union[Dict, str]]) -> Optional[httpx.Client]:
    """Build an httpx.Client for the given proxy settings.

    httpx >= 0.28 removed the ``proxies=`` argument: a single proxy is passed as
    ``proxy=`` and per-scheme proxies via ``mounts=``.
    """
    if not http_client_proxies:
        return None
    if isinstance(http_client_proxies, dict):
        return httpx.Client(
            mounts={scheme: httpx.HTTPTransport(proxy=url) for scheme, url in http_client_proxies.items()}
        )
    return httpx.Client(proxy=http_client_proxies)


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
        huggingface_base_url: Optional[str] = None,
        # AzureOpenAI specific
        azure_kwargs: Optional[AzureConfig] = None,
        http_client_proxies: Optional[Union[Dict, str]] = None,
        # VertexAI specific
        vertex_credentials_json: Optional[str] = None,
        memory_add_embedding_type: Optional[str] = None,
        memory_update_embedding_type: Optional[str] = None,
        memory_search_embedding_type: Optional[str] = None,
        # Gemini specific
        output_dimensionality: Optional[str] = None,
        # LM Studio specific
        lmstudio_base_url: Optional[str] = "http://localhost:1234/v1",
        # AWS Bedrock specific
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
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
        :param huggingface_base_url: Huggingface base URL to be use, defaults to None
        :type huggingface_base_url: Optional[str], optional
        :param openai_base_url: Openai base URL to be use, defaults to "https://api.openai.com/v1"
        :type openai_base_url: Optional[str], optional
        :param azure_kwargs: key-value arguments for the AzureOpenAI embedding model, defaults a dict inside init
        :type azure_kwargs: Optional[Dict[str, Any]], defaults a dict inside init
        :param http_client_proxies: The proxy server settings used to create self.http_client, defaults to None
        :type http_client_proxies: Optional[Dict | str], optional
        :param vertex_credentials_json: The path to the Vertex AI credentials JSON file, defaults to None
        :type vertex_credentials_json: Optional[str], optional
        :param memory_add_embedding_type: The type of embedding to use for the add memory action, defaults to None
        :type memory_add_embedding_type: Optional[str], optional
        :param memory_update_embedding_type: The type of embedding to use for the update memory action, defaults to None
        :type memory_update_embedding_type: Optional[str], optional
        :param memory_search_embedding_type: The type of embedding to use for the search memory action, defaults to None
        :type memory_search_embedding_type: Optional[str], optional
        :param lmstudio_base_url: LM Studio base URL to be use, defaults to "http://localhost:1234/v1"
        :type lmstudio_base_url: Optional[str], optional
        """

        self.model = model
        self.api_key = api_key
        self.openai_base_url = openai_base_url
        self.embedding_dims = embedding_dims

        # AzureOpenAI specific
        self.http_client_proxies = http_client_proxies
        self.http_client = _build_http_client(http_client_proxies)

        # Ollama specific
        self.ollama_base_url = ollama_base_url

        # Huggingface specific
        self.model_kwargs = model_kwargs or {}
        self.huggingface_base_url = huggingface_base_url
        # AzureOpenAI specific
        self.azure_kwargs = AzureConfig(**(azure_kwargs or {})) or {}

        # VertexAI specific
        self.vertex_credentials_json = vertex_credentials_json
        self.memory_add_embedding_type = memory_add_embedding_type
        self.memory_update_embedding_type = memory_update_embedding_type
        self.memory_search_embedding_type = memory_search_embedding_type

        # Gemini specific
        self.output_dimensionality = output_dimensionality

        # LM Studio specific
        self.lmstudio_base_url = lmstudio_base_url

        # AWS Bedrock specific
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region or os.environ.get("AWS_REGION") or "us-west-2"

