import os
from typing import Literal, Optional

from mem0.configs.embeddings.base import BaseEmbedderConfig
from mem0.embeddings.base import EmbeddingBase


class LiteLLMEmbedding(EmbeddingBase):
    """LiteLLM embedding provider supporting 100+ embedding models.
    
    Supports OpenAI, Azure, Bedrock, Vertex AI, Cohere, HuggingFace, and more
    through a unified interface.
    
    Example config:
        {
            "embedder": {
                "provider": "litellm",
                "config": {
                    "model": "text-embedding-3-small",  # or "azure/my-deployment", "bedrock/amazon.titan-embed-text-v1", etc.
                    "api_key": "your-api-key",  # optional, uses env vars by default
                    "api_base": "https://your-proxy.com",  # optional, for LiteLLM proxy
                }
            }
        }
    """

    def __init__(self, config: Optional[BaseEmbedderConfig] = None):
        super().__init__(config)
        
        try:
            import litellm
        except ImportError:
            raise ImportError(
                "litellm is required for LiteLLMEmbedding. "
                "Install it with: pip install litellm"
            )
        
        self.litellm = litellm
        self.config.model = self.config.model or "text-embedding-3-small"
        self.config.embedding_dims = self.config.embedding_dims or 1536
        
        # Optional API key override (litellm uses env vars by default)
        self.api_key = self.config.api_key or os.getenv("LITELLM_API_KEY")
        
        # Optional base URL for LiteLLM proxy
        self.api_base = getattr(self.config, 'api_base', None) or os.getenv("LITELLM_API_BASE")

    def embed(self, text: str, memory_action: Optional[Literal["add", "search", "update"]] = None):
        """
        Get the embedding for the given text using LiteLLM.

        Args:
            text (str): The text to embed.
            memory_action (optional): The type of embedding to use. Defaults to None.
            
        Returns:
            list: The embedding vector.
        """
        text = text.replace("\n", " ")
        
        kwargs = {
            "model": self.config.model,
            "input": [text],
        }
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.config.embedding_dims:
            kwargs["dimensions"] = self.config.embedding_dims
            
        response = self.litellm.embedding(**kwargs)
        return response.data[0]["embedding"]
