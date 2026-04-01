from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class BailianRerankerConfig(BaseRerankerConfig):
    """
    Configuration for DashScope reranker.

    Attributes:
        model (str): Model to use for reranking. Defaults to "qwen3-rerank".
        api_key (str): Dashscope API key. If not provided, will try to read DASHSCOPE_API_KEY from  environment variable.
        return_documents (boolean): Number of top documents to return after reranking.
        api_url (str): DashScope API URL. Defaults to "".
        top_k (int): Number of top documents to return after reranking.
    """

    model: str = Field(
        default="qwen3-rerank",
        description="Model to use for reranking. Available models: qwen3-rerank, gte-rerank-v2",
    )
    api_key: Optional[str] = Field(default=None, description="DashScope API key")
    api_url: Optional[str] = Field(default=None, description="reranker API URL")
    return_documents: Optional[bool] = Field(
        default=True, description="return documents(Only for gte-rerank-v2)"
    )
    top_k: Optional[int] = Field(
        default=100, description="Number of top documents to return after reranking"
    )
