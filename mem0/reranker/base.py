from abc import ABC, abstractmethod
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def log_reranker_fallback(provider: str, exc: Exception) -> None:
    """Log reranker failures before preserving the existing fallback behavior."""
    logger.warning(
        "%s reranking failed; returning fallback rerank scores.",
        provider,
        exc_info=exc,
    )


class BaseReranker(ABC):
    """Abstract base class for all rerankers."""

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
