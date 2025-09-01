from abc import ABC
from typing import Optional


class BaseRerankerConfig(ABC):
    """
    Base configuration for rerankers with only common parameters.
    Provider-specific configurations should be handled by separate config classes.

    This class contains only the parameters that are common across all reranker providers.
    For provider-specific parameters, use the appropriate provider config class.
    """

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        top_k: Optional[int] = None,
    ):
        """
        Initialize a base configuration class instance for the reranker.

        Args:
            model (str, optional): The reranker model to use.
            api_key (str, optional): The API key for the reranker service.
            top_k (int, optional): Maximum number of documents to return after reranking.
        """
        self.model = model
        self.api_key = api_key
        self.top_k = top_k