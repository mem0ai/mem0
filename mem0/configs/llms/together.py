from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class TogetherConfig(BaseLlmConfig):
    """
    Configuration class for Together-specific parameters.
    Inherits from BaseLlmConfig and adds Together-specific settings.
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
        # Together-specific parameters
        together_base_url: Optional[str] = None,
    ):
        """
        Initialize Together configuration.

        Args:
            model: Together model to use, defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: Together API key, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            together_base_url: Together API base URL, defaults to None
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

        # Together-specific parameters
        self.together_base_url = together_base_url
