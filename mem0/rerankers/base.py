"""Base reranker class for all reranker implementations."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class RerankerResult(BaseModel):
    """Result from a reranker operation."""
    
    id: str
    score: float
    rank: int
    content: str


class BaseReranker(ABC):
    """Abstract base class for all reranker implementations."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the reranker with configuration.
        
        Args:
            config: Configuration dictionary containing provider-specific settings
        """
        self.config = config
    
    @abstractmethod
    def rerank(
        self, 
        query: str, 
        documents: List[Dict[str, Any]], 
        top_n: Optional[int] = None
    ) -> List[RerankerResult]:
        """Rerank documents based on query relevance.
        
        Args:
            query: The search query
            documents: List of documents to rerank, each containing at least 'id' and 'memory' fields
            top_n: Number of top results to return (if None, return all)
            
        Returns:
            List of reranked results with scores
        """
        pass
    
    def _prepare_documents(self, documents: List[Dict[str, Any]]) -> List[str]:
        """Prepare documents for reranking by extracting text content.
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            List of text content from documents
        """
        texts = []
        for doc in documents:
            # Extract text content, prioritizing 'memory' field, then 'data'
            text = doc.get('memory', doc.get('data', doc.get('content', '')))
            texts.append(text)
        return texts

