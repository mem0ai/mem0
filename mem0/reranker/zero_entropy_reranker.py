import os
from typing import List, Dict, Any

from mem0.reranker.base import BaseReranker

try:
    from zeroentropy import ZeroEntropy
    ZERO_ENTROPY_AVAILABLE = True
except ImportError:
    ZERO_ENTROPY_AVAILABLE = False


class ZeroEntropyReranker(BaseReranker):
    """Zero Entropy-based reranker implementation."""
    
    def __init__(self, config):
        """
        Initialize Zero Entropy reranker.
        
        Args:
            config: ZeroEntropyRerankerConfig object with configuration parameters
        """
        if not ZERO_ENTROPY_AVAILABLE:
            raise ImportError("zeroentropy package is required for ZeroEntropyReranker. Install with: pip install zeroentropy")
        
        self.config = config
        self.api_key = config.api_key or os.getenv("ZERO_ENTROPY_API_KEY")
        if not self.api_key:
            raise ValueError("Zero Entropy API key is required. Set ZERO_ENTROPY_API_KEY environment variable or pass api_key in config.")
            
        self.model = config.model or "zerank-1"
        
        # Initialize Zero Entropy client
        if self.api_key:
            self.client = ZeroEntropy(api_key=self.api_key)
        else:
            self.client = ZeroEntropy()  # Will use ZERO_ENTROPY_API_KEY from environment
        
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using Zero Entropy's rerank API.
        
        Args:
            query: The search query
            documents: List of documents to rerank
            top_k: Number of top documents to return
            
        Returns:
            List of reranked documents with rerank_score
        """
        if not documents:
            return documents
            
        # Extract text content for reranking
        doc_texts = []
        for doc in documents:
            if 'memory' in doc:
                doc_texts.append(doc['memory'])
            elif 'text' in doc:
                doc_texts.append(doc['text'])  
            elif 'content' in doc:
                doc_texts.append(doc['content'])
            else:
                doc_texts.append(str(doc))
        
        try:
            # Call Zero Entropy rerank API
            response = self.client.models.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
            )
            
            # Create reranked results
            reranked_docs = []
            for result in response.results:
                original_doc = documents[result.index].copy()
                original_doc['rerank_score'] = result.relevance_score
                reranked_docs.append(original_doc)
            
            # Sort by relevance score in descending order
            reranked_docs.sort(key=lambda x: x['rerank_score'], reverse=True)
            
            # Apply top_k limit
            if top_k:
                reranked_docs = reranked_docs[:top_k]
            elif self.config.top_k:
                reranked_docs = reranked_docs[:self.config.top_k]
                
            return reranked_docs

        except Exception:
            # Fallback to original order if reranking fails
            for doc in documents:
                doc['rerank_score'] = 0.0
            return documents[:top_k] if top_k else documents