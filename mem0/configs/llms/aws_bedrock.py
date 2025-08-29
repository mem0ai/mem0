import os
from typing import Any, Dict, List, Optional

from mem0.configs.llms.base import BaseLlmConfig


class AWSBedrockConfig(BaseLlmConfig):
    """
    Configuration class for AWS Bedrock LLM integration.

    Supports all available Bedrock models with automatic provider detection.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2000,
        top_p: float = 0.9,
        top_k: int = 1,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: str = "",
        aws_session_token: Optional[str] = None,
        aws_profile: Optional[str] = None,
        model_kwargs: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        """
        Initialize AWS Bedrock configuration.

        Args:
            model: Bedrock model identifier (e.g., "amazon.nova-3-mini-20241119-v1:0")
            temperature: Controls randomness (0.0 to 2.0)
            max_tokens: Maximum tokens to generate
            top_p: Nucleus sampling parameter (0.0 to 1.0)
            top_k: Top-k sampling parameter (1 to 40)
            aws_access_key_id: AWS access key (optional, uses env vars if not provided)
            aws_secret_access_key: AWS secret key (optional, uses env vars if not provided)
            aws_region: AWS region for Bedrock service
            aws_session_token: AWS session token for temporary credentials
            aws_profile: AWS profile name for credentials
            model_kwargs: Additional model-specific parameters
            **kwargs: Additional arguments passed to base class
        """
        super().__init__(
            model=model or "anthropic.claude-3-5-sonnet-20240620-v1:0",
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            **kwargs,
        )

        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_region = aws_region or os.getenv("AWS_REGION", "us-west-2")
        self.aws_session_token = aws_session_token
        self.aws_profile = aws_profile
        self.model_kwargs = model_kwargs or {}

    @property
    def provider(self) -> str:
        """Get the provider from the model identifier."""
        if not self.model or "." not in self.model:
            return "unknown"
        return self.model.split(".")[0]

    @property
    def model_name(self) -> str:
        """Get the model name without provider prefix."""
        if not self.model or "." not in self.model:
            return self.model
        return ".".join(self.model.split(".")[1:])

    def get_model_config(self) -> Dict[str, Any]:
        """Get model-specific configuration parameters."""
        base_config = {
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "top_k": self.top_k,
        }

        # Add custom model kwargs
        base_config.update(self.model_kwargs)

        return base_config

    def get_aws_config(self) -> Dict[str, Any]:
        """Get AWS configuration parameters."""
        config = {
            "region_name": self.aws_region,
        }

        if self.aws_access_key_id:
            config["aws_access_key_id"] = self.aws_access_key_id or os.getenv("AWS_ACCESS_KEY_ID")
            
        if self.aws_secret_access_key:
            config["aws_secret_access_key"] = self.aws_secret_access_key or os.getenv("AWS_SECRET_ACCESS_KEY")
            
        if self.aws_session_token:
            config["aws_session_token"] = self.aws_session_token or os.getenv("AWS_SESSION_TOKEN")
            
        if self.aws_profile:
            config["profile_name"] = self.aws_profile or os.getenv("AWS_PROFILE")

        return config

    def validate_model_format(self) -> bool:
        """
        Validate that the model identifier follows Bedrock naming convention.
        
        Returns:
            True if valid, False otherwise
        """
        if not self.model:
            return False
            
        # Check if model follows provider.model-name format
        if "." not in self.model:
            return False
            
        provider, model_name = self.model.split(".", 1)
        
        # Validate provider
        valid_providers = [
            "ai21", "amazon", "anthropic", "cohere", "meta", "mistral", 
            "stability", "writer", "deepseek", "gpt-oss", "perplexity", 
            "snowflake", "titan", "command", "j2", "llama"
        ]
        
        if provider not in valid_providers:
            return False
            
        # Validate model name is not empty
        if not model_name:
            return False
            
        return True

    def get_supported_regions(self) -> List[str]:
        """Get list of AWS regions that support Bedrock."""
        return [
            "us-east-1",
            "us-west-2",
            "us-east-2",
            "eu-west-1",
            "ap-southeast-1",
            "ap-northeast-1",
        ]

    def get_model_capabilities(self) -> Dict[str, Any]:
        """Get model capabilities based on provider."""
        capabilities = {
            "supports_tools": False,
            "supports_vision": False,
            "supports_streaming": False,
            "supports_multimodal": False,
        }
        
        if self.provider == "anthropic":
            capabilities.update({
                "supports_tools": True,
                "supports_vision": True,
                "supports_streaming": True,
                "supports_multimodal": True,
            })
        elif self.provider == "amazon":
            capabilities.update({
                "supports_tools": True,
                "supports_vision": True,
                "supports_streaming": True,
                "supports_multimodal": True,
            })
        elif self.provider == "cohere":
            capabilities.update({
                "supports_tools": True,
                "supports_streaming": True,
            })
        elif self.provider == "meta":
            capabilities.update({
                "supports_vision": True,
                "supports_streaming": True,
            })
        elif self.provider == "mistral":
            capabilities.update({
                "supports_vision": True,
                "supports_streaming": True,
            })
            
        return capabilities
