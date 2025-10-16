from typing import Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class SentenceTransformerRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for Sentence Transformer reranker-specific parameters.
    Inherits from BaseRerankerConfig and adds Sentence Transformer-specific settings.
    """

    model: Optional[str] = Field(default="cross-encoder/ms-marco-MiniLM-L-6-v2", description="The cross-encoder model name to use")
    device: Optional[str] = Field(default=None, description="Device to run the model on ('cpu', 'cuda', etc.)")
    batch_size: int = Field(default=32, description="Batch size for processing documents")
    show_progress_bar: bool = Field(default=False, description="Whether to show progress bar during processing")
