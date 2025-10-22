import os
from typing import List, Dict, Any

from mem0.reranker.base import BaseReranker

try:
    import cohere
    COHERE_AVAILABLE = True
except ImportError:
    COHERE_AVAILABLE = False


class CohereReranker(BaseReranker):
    """Cohere-based reranker implementation."""
    
    def __init__(self, config):
        """
        Initialize Cohere reranker.
        
        Args:
            config: CohereRerankerConfig object with configuration parameters
        """
        if not COHERE_AVAILABLE:
            raise ImportError("cohere package is required for CohereReranker. Install with: pip install cohere")
        
        self.config = config
        self.api_key = config.api_key or os.getenv("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError("Cohere API key is required. Set COHERE_API_KEY environment variable or pass api_key in config.")
            
        self.model = config.model
        self.client = cohere.Client(self.api_key)
        
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using Cohere's rerank API.
        
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
            # Call Cohere rerank API
            response = self.client.rerank(
                model=self.model,
                query=query,
                documents=doc_texts,
                top_n=top_k or self.config.top_k or len(documents),
                return_documents=self.config.return_documents,
                max_chunks_per_doc=self.config.max_chunks_per_doc,
            )
            
            # Create reranked results
            reranked_docs = []
            for result in response.results:
                original_doc = documents[result.index].copy()
                original_doc['rerank_score'] = result.relevance_score
                reranked_docs.append(original_doc)
                
            return reranked_docs

        except Exception:
            # Fallback to original order if reranking fails
            for doc in documents:
                doc['rerank_score'] = 0.0
            return documents[:top_k] if top_k else documents