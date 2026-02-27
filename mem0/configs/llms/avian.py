from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class AvianConfig(BaseLlmConfig):
    """
    Configuration class for Avian-specific parameters.
    Inherits from BaseLlmConfig and adds Avian-specific settings.
    """

    def __init__(
        self,
        # Base parameters
        model: Optional[str] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 2000,
        top_p: float = 0.1,
        top_k: int = 1,
        enable_vision: bool = False,
        vision_details: Optional[str] = "auto",
        http_client_proxies: Optional[dict] = None,
        # Avian-specific parameters
        avian_base_url: Optional[str] = None,
    ):
        """
        Initialize Avian configuration.

        Args:
            model: Avian model to use, defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: Avian API key, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            avian_base_url: Avian API base URL, defaults to None
        """
        # Initialize base parameters
        super().__init__(
            model=model,
            temperature=temperature,
            api_key=api_key,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            enable_vision=enable_vision,
            vision_details=vision_details,
            http_client_proxies=http_client_proxies,
        )

        # Avian-specific parameters
        self.avian_base_url = avian_base_url
