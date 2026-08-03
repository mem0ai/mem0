from typing import Dict, Optional

from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class OpenAICompatibleRerankerConfig(BaseRerankerConfig):
    """
    Configuration for a self-hosted or third-party reranker that exposes an
    OpenAI/Cohere-compatible ``/rerank`` HTTP endpoint (e.g. bge-reranker, Jina,
    Voyage, SiliconFlow, Together, or a vLLM-hosted reranker).

    Inherits ``provider``, ``model``, ``api_key`` and ``top_k`` from
    :class:`BaseRerankerConfig` and adds the endpoint-specific settings.
    """

    base_url: str = Field(
        description="Base URL of the reranker service exposing a `/rerank` endpoint, e.g. https://host/v1",
    )
    timeout: float = Field(default=60.0, description="Request timeout in seconds")
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="Extra HTTP headers to send with each rerank request"
    )
