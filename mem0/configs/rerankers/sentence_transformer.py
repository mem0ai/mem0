from typing import Optional

from mem0.configs.rerankers.base import BaseRerankerConfig


class SentenceTransformerRerankerConfig(BaseRerankerConfig):
    """
    Configuration class for Sentence Transformer reranker-specific parameters.
    Inherits from BaseRerankerConfig and adds Sentence Transformer-specific settings.
    """

    def __init__(
        self,
        # Base parameters
        model: Optional[str] = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        api_key: Optional[str] = None,  # Not used for sentence transformers
        top_k: Optional[int] = None,
        # Sentence Transformer-specific parameters
        device: Optional[str] = None,
        batch_size: int = 32,
        show_progress_bar: bool = False,
    ):
        """
        Initialize Sentence Transformer reranker configuration.

        Args:
            model (str): The cross-encoder model name to use.
            api_key (str, optional): Not used for sentence transformers.
            top_k (int, optional): Maximum number of documents to return after reranking.
            device (str, optional): Device to run the model on ('cpu', 'cuda', etc.).
            batch_size (int): Batch size for processing documents.
            show_progress_bar (bool): Whether to show progress bar during processing.
        """
        super().__init__(model=model, api_key=api_key, top_k=top_k)
        self.device = device
        self.batch_size = batch_size
        self.show_progress_bar = show_progress_bar