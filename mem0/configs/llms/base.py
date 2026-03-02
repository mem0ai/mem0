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
        together_base_url: Optional[str] = None,
        deepseek_base_url: Optional[str] = None,
        xai_base_url: Optional[str] = None,
        sarvam_base_url: Optional[str] = None,
        lmstudio_base_url: Optional[str] = None,
        lmstudio_response_format: Optional[Dict] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        aws_profile: Optional[str] = None,
    ):
        """
        Initialize a base configuration class instance for the LLM.

        Args:
            model: The model identifier to use (e.g., "gpt-4.1-nano-2025-04-14", "claude-3-5-sonnet-20240620")
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
            together_base_url: Optional Together base URL override.
            deepseek_base_url: Optional DeepSeek base URL override.
            xai_base_url: Optional xAI base URL override.
            sarvam_base_url: Optional Sarvam base URL override.
            lmstudio_base_url: Optional LM Studio base URL override.
            lmstudio_response_format: Optional LM Studio response format payload.
            aws_access_key_id: Optional AWS access key for Bedrock.
            aws_secret_access_key: Optional AWS secret key for Bedrock.
            aws_region: Optional AWS region for Bedrock.
            aws_session_token: Optional AWS session token.
            aws_profile: Optional AWS profile name.
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
        self.together_base_url = together_base_url
        self.deepseek_base_url = deepseek_base_url
        self.xai_base_url = xai_base_url
        self.sarvam_base_url = sarvam_base_url
        self.lmstudio_base_url = lmstudio_base_url
        self.lmstudio_response_format = lmstudio_response_format
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region
        self.aws_session_token = aws_session_token
        self.aws_profile = aws_profile
