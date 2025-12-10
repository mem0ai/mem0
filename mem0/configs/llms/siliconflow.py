from typing import Any, Callable, Optional

from mem0.configs.llms.base import BaseLlmConfig


class SiliconFlowConfig(BaseLlmConfig):
    """
    Configuration class for SiliconFlow-specific parameters.
    Inherits from BaseLlmConfig and adds SiliconFlow-specific settings.
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
        # SiliconFlow-specific parameters
        base_url: Optional[str] = None,
        # Response monitoring callback
        response_callback: Optional[Callable[[Any, dict, dict], None]] = None,
    ):
        """
        Initialize SiliconFlow configuration.

        Args:
            model: SiliconFlow model to use, defaults to "Qwen/Qwen2.5-7B-Instruct"
            temperature: Controls randomness, defaults to 0.1
            api_key: SiliconFlow API key, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            base_url: SiliconFlow API base URL, defaults to "https://api.siliconflow.com/v1"
            response_callback: Optional callback for monitoring LLM responses.
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

        # SiliconFlow-specific parameters
        self.base_url = base_url

        # Response monitoring
        self.response_callback = response_callback
