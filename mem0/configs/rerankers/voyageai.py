from typing import Optional

from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class VoyageAIRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for VoyageAI reranker-specific parameters.
    Inherits from BaseRerankerConfig and adds VoyageAI-specific settings.
    """

    model: Optional[str] = Field(
        default="rerank-2",
        description="The VoyageAI rerank model to use (rerank-2, rerank-2-lite)",
    )
    truncation: bool = Field(
        default=True,
        description="Whether to truncate documents that exceed the context window",
    )
