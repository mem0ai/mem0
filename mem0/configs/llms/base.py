from abc import ABC
from typing import Dict, Optional, Union

import httpx


class BaseLlmConfig(ABC):
    """
    Base configuration for LLMs with only common parameters.
    Provider-specific configurations should be handled by separate config classes.

    This class contains only the parameters that are common across all LLM providers.
    For provider-specific parameters, use the appropriate provider config class.
    """

    def __init__(
        self,
        model: Optional[Union[str, Dict]] = None,
        temperature: float = 0.1,
        api_key: Optional[str] = None,
        max_tokens: int = 2000,
        top_p: float = 0.1,
        top_k: int = 1,
        enable_vision: bool = False,
        vision_details: Optional[str] = "auto",
        http_client_proxies: Optional[Union[Dict, str]] = None,
    ):
        """
        Initialize a base configuration class instance for the LLM.

        Args:
            model: The model identifier to use (e.g., "gpt-4o-mini", "claude-3-5-sonnet-20240620")
                Defaults to None (will be set by provider-specific configs)
            temperature: Controls the randomness of the model's output.
                Higher values (closer to 1) make output more random, lower values make it more deterministic.
                Range: 0.0 to 2.0. Defaults to 0.1
            api_key: API key for the LLM provider. If None, will try to get from environment variables.
                Defaults to None
            max_tokens: Maximum number of tokens to generate in the response.
                Range: 1 to 4096 (varies by model). Defaults to 2000
            top_p: Nucleus sampling parameter. Controls diversity via nucleus sampling.
                Higher values (closer to 1) make word selection more diverse.
                Range: 0.0 to 1.0. Defaults to 0.1
            top_k: Top-k sampling parameter. Limits the number of tokens considered for each step.
                Higher values make word selection more diverse.
                Range: 1 to 40. Defaults to 1
            enable_vision: Whether to enable vision capabilities for the model.
                Only applicable to vision-enabled models. Defaults to False
            vision_details: Level of detail for vision processing.
                Options: "low", "high", "auto". Defaults to "auto"
            http_client_proxies: Proxy settings for HTTP client.
                Can be a dict or string. Defaults to None
        """
        self.model = model
        self.temperature = temperature
        self.api_key = api_key
        self.max_tokens = max_tokens
        self.top_p = top_p
        self.top_k = top_k
        self.enable_vision = enable_vision
        self.vision_details = vision_details
        self.http_client = httpx.Client(proxies=http_client_proxies) if http_client_proxies else None
