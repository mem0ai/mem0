from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class TEIRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for TEI (Text Embeddings Inference) reranker.
    """

    base_url: str = Field(default="http://localhost:8184", description="Base URL of the TEI rerank endpoint")
    top_k: Optional[int] = Field(default=None, description="Maximum number of documents to return after reranking")
    timeout: int = Field(default=10, description="HTTP request timeout in seconds")
