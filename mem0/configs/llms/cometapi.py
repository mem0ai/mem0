from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class CometAPIConfig(BaseLlmConfig):
    """
    Configuration class for CometAPI-specific parameters.
    Inherits from BaseLlmConfig and adds CometAPI-specific settings.
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
        # CometAPI-specific parameters
        cometapi_base_url: Optional[str] = None,
    ):
        """
        Initialize CometAPI configuration.

        Args:
            model: CometAPI model to use, defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: CometAPI API key (COMETAPI_KEY), defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            cometapi_base_url: CometAPI base URL, defaults to "https://api.cometapi.com/v1/"
        """
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
        self.cometapi_base_url = cometapi_base_url or "https://api.cometapi.com/v1/"
