from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseReranker(ABC):
    """Abstract base class for all rerankers."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize the reranker with configuration.

        Args:
            config: Configuration dictionary for the reranker
        """
        self.config = config

    @abstractmethod
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents based on relevance to the query.

        Args:
            query: The search query
            documents: List of documents to rerank, each with 'memory' field
            top_k: Number of top documents to return (None = return all)

        Returns:
            List of reranked documents with added 'rerank_score' field
        """
        pass
