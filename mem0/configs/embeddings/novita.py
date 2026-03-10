from typing import Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig


class NovitaEmbeddingConfig(BaseEmbedderConfig):
    """
    Configuration class for Novita-specific embedding parameters.
    Inherits from BaseEmbedderConfig and adds Novita-specific settings.
    """

    def __init__(
        self,
        # Base parameters
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        embedding_dims: Optional[int] = None,
        # OpenAI-compatible base URL option
        openai_base_url: Optional[str] = None,
        # Novita-specific parameters
        novita_base_url: Optional[str] = None,
        http_client_proxies: Optional[str] = None,
    ):
        """
        Initialize Novita embedding configuration.

        Args:
            model: Novita embedding model to use, defaults to None
            api_key: Novita API key, defaults to None
            embedding_dims: Number of embedding dimensions, defaults to None
            openai_base_url: OpenAI-compatible base URL, defaults to None
            novita_base_url: Novita-specific base URL, defaults to None
            http_client_proxies: HTTP client proxy settings, defaults to None
        """
        # Initialize base parameters
        super().__init__(
            model=model,
            api_key=api_key,
            embedding_dims=embedding_dims,
            openai_base_url=openai_base_url,
            http_client_proxies=http_client_proxies,
        )

        # Novita-specific parameters
        self.novita_base_url = novita_base_url
