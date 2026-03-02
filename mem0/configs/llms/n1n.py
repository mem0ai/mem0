from typing import Any, Dict, Optional

from mem0.configs.llms.base import BaseLlmConfig


class N1NConfig(BaseLlmConfig):
    """
    Configuration class for n1n API-specific parameters.
    n1n provides access to 400+ LLM models through an OpenAI-compatible API.
    
    Inherits from BaseLlmConfig and adds n1n-specific settings.
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
        # n1n-specific parameters
        n1n_base_url: Optional[str] = None,
        n1n_response_format: Optional[Dict[str, Any]] = None,
    ):
        """
        Initialize n1n API configuration.

        Args:
            model: n1n model to use (e.g., "gpt-4", "claude-3-5-sonnet-20241022", etc.)
                See https://n1n.ai/pricing for available models, defaults to "gpt-4o-mini"
            temperature: Controls randomness (0-1), defaults to 0.1
            api_key: n1n API key (get from https://n1n.ai/console), defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter (0-1), defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities for multimodal models, defaults to False
            vision_details: Vision detail level ("auto", "low", "high"), defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            n1n_base_url: n1n API base URL, defaults to "https://n1n.ai/v1"
            n1n_response_format: n1n response format settings, defaults to None
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

        # Set n1n-specific parameters
        self.n1n_base_url = n1n_base_url or "https://n1n.ai/v1"
        self.n1n_response_format = n1n_response_format
