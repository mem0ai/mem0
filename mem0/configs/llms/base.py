from abc import ABC
from typing import Dict, Optional, Union

import httpx

from mem0.configs.base import AzureConfig


class BaseLlmConfig(ABC):
    """
    Config for LLMs.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 2000,
        top_p: float = 0.1,
        top_k: int = 1,
        # Openrouter specific
        models: Optional[list[str]] = None,
        route: Optional[str] = "fallback",
        openrouter_base_url: Optional[str] = None,
        # Openai specific
        openai_base_url: Optional[str] = None,
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,
        # Ollama specific
        ollama_base_url: Optional[str] = None,
        # AzureOpenAI specific
        azure_kwargs: Optional[AzureConfig] = {},
        # AzureOpenAI specific
        http_client_proxies: Optional[Union[Dict, str]] = None,
        # DeepSeek specific
        deepseek_base_url: Optional[str] = None,
        # XAI specific
        xai_base_url: Optional[str] = None,
    ):
        """
        Initializes a configuration class instance for the LLM.

        :param model: Controls the OpenAI model used, defaults to None
        :type model: Optional[str], optional
        :param temperature:  Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random, lower values make it more deterministic, defaults to 0
        :type temperature: float, optional
        :param api_key: OpenAI API key to be use, defaults to None
        :type api_key: Optional[str], optional
        :param max_tokens: Controls how many tokens are generated, defaults to 2000
        :type max_tokens: int, optional
        :param top_p: Controls the diversity of words. Higher values (closer to 1) make word selection more diverse,
        defaults to 1
        :type top_p: float, optional
        :param top_k: Controls the diversity of words. Higher values make word selection more diverse, defaults to 0
        :type top_k: int, optional
        :param models: Openrouter models to use, defaults to None
        :type models: Optional[list[str]], optional
        :param route: Openrouter route to be used, defaults to "fallback"
        :type route: Optional[str], optional
        :param openrouter_base_url: Openrouter base URL to be use, defaults to "https://openrouter.ai/api/v1"
        :type openrouter_base_url: Optional[str], optional
        :param site_url: Openrouter site URL to use, defaults to None
        :type site_url: Optional[str], optional
        :param app_name: Openrouter app name to use, defaults to None
        :type app_name: Optional[str], optional
        :param ollama_base_url: The base URL of the LLM, defaults to None
        :type ollama_base_url: Optional[str], optional
        :param openai_base_url: Openai base URL to be use, defaults to "https://api.openai.com/v1"
        :type openai_base_url: Optional[str], optional
        :param azure_kwargs: key-value arguments for the AzureOpenAI LLM model, defaults a dict inside init
        :type azure_kwargs: Optional[Dict[str, Any]], defaults a dict inside init
        :param http_client_proxies: The proxy server(s) settings used to create self.http_client, defaults to None
        :type http_client_proxies: Optional[Dict | str], optional
        :param deepseek_base_url: DeepSeek base URL to be use, defaults to None
        :type deepseek_base_url: Optional[str], optional
        :param xai_base_url: XAI base URL to be use, defaults to None
        :type xai_base_url: Optional[str], optional
        """

        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k

        # AzureOpenAI specific
        self.http_client = httpx.Client(proxies=http_client_proxies) if http_client_proxies else None

        # Openrouter specific
        self.models = models
        self.route = route
        self.openrouter_base_url = openrouter_base_url
        self.openai_base_url = openai_base_url
        self.site_url = site_url
        self.app_name = app_name

        # Ollama specific
        self.ollama_base_url = ollama_base_url

        # DeepSeek specific
        self.deepseek_base_url = deepseek_base_url

        # AzureOpenAI specific
        self.azure_kwargs = AzureConfig(**azure_kwargs) or {}

        # XAI specific
        self.xai_base_url = xai_base_url
