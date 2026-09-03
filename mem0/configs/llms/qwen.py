from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class QwenConfig(BaseLlmConfig):
    """
    Configuration class for Alibaba Cloud Qwen (DashScope) LLM.
    Inherits from BaseLlmConfig and adds Qwen-specific settings.
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
        # Qwen-specific parameters
        qwen_base_url: Optional[str] = None,
    ):
        """
        Initialize Qwen configuration.

        Args:
            model (Optional[str]): Qwen model name (e.g., "qwen-turbo", "qwen-plus", "qwen-max")
            temperature (float): Sampling temperature
            api_key (Optional[str]): DashScope API key
            max_tokens (int): Maximum tokens to generate
            top_p (float): Nucleus sampling parameter
            top_k (int): Top-k sampling parameter
            enable_vision (bool): Enable vision capabilities
            vision_details (Optional[str]): Vision detail level
            http_client_proxies (Optional[dict]): HTTP client proxies
            qwen_base_url (Optional[str]): Custom base URL for Qwen API
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
        self.qwen_base_url = qwen_base_url
