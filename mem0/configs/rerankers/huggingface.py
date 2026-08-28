from typing import Any, Dict, Optional
from pydantic import Field

from mem0.configs.rerankers.base import BaseRerankerConfig


class HuggingFaceRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for HuggingFace reranker-specific parameters.
    Inherits from BaseRerankerConfig and adds HuggingFace-specific settings.
    """

    model: Optional[str] = Field(default="BAAI/bge-reranker-base", description="The HuggingFace model to use for reranking")
    device: Optional[str] = Field(default=None, description="Device to run the model on ('cpu', 'cuda', etc.)")
    batch_size: int = Field(default=32, description="Batch size for processing documents")
    max_length: int = Field(default=512, description="Maximum length for tokenization")
    normalize: bool = Field(default=True, description="Whether to normalize scores")
    trust_remote_code: bool = Field(default=False, description="Whether to allow custom remote code when loading the model")
    model_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Additional kwargs for model loading (e.g. torch_dtype)")
    use_auth_token: Optional[str] = Field(default=None, description="Auth token for private/gated models")
    local_files_only: bool = Field(default=False, description="Only load from local files, do not download")
