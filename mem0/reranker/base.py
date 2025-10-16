from abc import ABC, abstractmethod
from typing import List, Dict, Any

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