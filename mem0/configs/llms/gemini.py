import os
from typing import Optional

from mem0.configs.llms.base import BaseLlmConfig


class GeminiConfig(BaseLlmConfig):
    """
    Configuration class for Google Gemini LLM.

    Supports both the Gemini Developer API (via API key) and Vertex AI (via GCP credentials).
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
        # Gemini-specific parameters
        vertexai: Optional[bool] = None,
        project: Optional[str] = None,
        location: Optional[str] = None,
    ):
        """
        Initialize Gemini configuration.

        Args:
            model: Gemini model to use (e.g., "gemini-2.0-flash"), defaults to None
            temperature: Controls randomness, defaults to 0.1
            api_key: Google API key for the Gemini Developer API, defaults to None
            max_tokens: Maximum tokens to generate, defaults to 2000
            top_p: Nucleus sampling parameter, defaults to 0.1
            top_k: Top-k sampling parameter, defaults to 1
            enable_vision: Enable vision capabilities, defaults to False
            vision_details: Vision detail level, defaults to "auto"
            http_client_proxies: HTTP client proxy settings, defaults to None
            vertexai: Whether to use Vertex AI backend. If None, checks GOOGLE_GENAI_USE_VERTEXAI env var.
            project: GCP project ID for Vertex AI. If None, checks GOOGLE_CLOUD_PROJECT env var.
            location: GCP location for Vertex AI. If None, checks GOOGLE_CLOUD_LOCATION env var.
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

        if vertexai is None:
            vertexai = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower() in ("true", "1", "yes")
        self.vertexai = vertexai
        self.project = project or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.location = location or os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")