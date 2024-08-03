from abc import ABC
from typing import Optional

class BaseLlmConfig(ABC):
    """
    Config for LLMs.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0,
        max_tokens: int = 3000,
        top_p: float = 0,
        top_k: int = 1,

        # Openrouter specific
        models: Optional[list[str]] = None,
        route: Optional[str] = "fallback",
        openrouter_base_url: Optional[str] = "https://openrouter.ai/api/v1",
        site_url: Optional[str] = None,
        app_name: Optional[str] = None,

        # Ollama specific
        ollama_base_url: Optional[str] = None
    ):
        """
        Initializes a configuration class instance for the LLM.

        :param model: Controls the OpenAI model used, defaults to None
        :type model: Optional[str], optional
        :param temperature:  Controls the randomness of the model's output.
        Higher values (closer to 1) make output more random, lower values make it more deterministic, defaults to 0
        :type temperature: float, optional
        :param max_tokens: Controls how many tokens are generated, defaults to 3000
        :type max_tokens: int, optional
        :param top_p: Controls the diversity of words. Higher values (closer to 1) make word selection more diverse,
        defaults to 1
        :type top_p: float, optional
        :param top_k: Controls the diversity of words. Higher values make word selection more diverse, defaults to 0
        :type top_k: int, optional
        :param models: Controls the Openrouter models used, defaults to None
        :type models: Optional[list[str]], optional
        :param route: Controls the Openrouter route used, defaults to "fallback"
        :type route: Optional[str], optional
        :param openrouter_base_url: Controls the Openrouter base URL used, defaults to "https://openrouter.ai/api/v1"
        :type openrouter_base_url: Optional[str], optional
        :param site_url: Controls the Openrouter site URL used, defaults to None
        :type site_url: Optional[str], optional
        :param app_name: Controls the Openrouter app name used, defaults to None
        :type app_name: Optional[str], optional
        :param ollama_base_url: The base URL of the LLM, defaults to None
        :type ollama_base_url: Optional[str], optional
        """
        
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k

        # Openrouter specific
        self.models = models
        self.route = route
        self.openrouter_base_url = openrouter_base_url
        self.site_url = site_url
        self.app_name = app_name

        # Ollama specific
        self.ollama_base_url = ollama_base_url
