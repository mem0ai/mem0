from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class ZhipuConfig(BaseLlmConfig):
    """
    Configuration class for Zhipu AI (GLM) LLM.
    Inherits from BaseLlmConfig and adds Zhipu-specific settings.
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
        # Zhipu-specific parameters
        zhipu_base_url: Optional[str] = None,
    ):
        """
        Initialize Zhipu configuration.

        Args:
            model (Optional[str]): Zhipu model name (e.g., "glm-4", "glm-4-plus", "glm-4-flash")
            temperature (float): Sampling temperature
            api_key (Optional[str]): Zhipu AI API key
            max_tokens (int): Maximum tokens to generate
            top_p (float): Nucleus sampling parameter
            top_k (int): Top-k sampling parameter
            enable_vision (bool): Enable vision capabilities
            vision_details (Optional[str]): Vision detail level
            http_client_proxies (Optional[dict]): HTTP client proxies
            zhipu_base_url (Optional[str]): Custom base URL for Zhipu API
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
        self.zhipu_base_url = zhipu_base_url
