import os
from typing import Any, Dict, List

from mem0.reranker.base import BaseReranker


class VoyageAIReranker(BaseReranker):
    """VoyageAI-based reranker implementation."""

    def __init__(self, config):
        """
        Initialize VoyageAI reranker.

        Args:
            config: VoyageAIRerankerConfig object with configuration parameters
        """
        try:
            import voyageai
        except ImportError:
            raise ImportError(
                "voyageai package is required for VoyageAIReranker. "
                "Install with: pip install voyageai"
            )

        self.config = config
        self.api_key = config.api_key or os.getenv("VOYAGE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "VoyageAI API key is required. Set VOYAGE_API_KEY environment variable "
                "or pass api_key in config."
            )

        self.model = config.model or "rerank-2"
        self.truncation = getattr(config, "truncation", True)
        self.client = voyageai.Client(api_key=self.api_key)

    def rerank(
        self, query: str, documents: List[Dict[str, Any]], top_k: int = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using VoyageAI's rerank API.

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
            if "memory" in doc:
                doc_texts.append(doc["memory"])
            elif "text" in doc:
                doc_texts.append(doc["text"])
            elif "content" in doc:
                doc_texts.append(doc["content"])
            else:
                doc_texts.append(str(doc))

        try:
            # Call VoyageAI rerank API
            response = self.client.rerank(
                query=query,
                documents=doc_texts,
                model=self.model,
                top_k=top_k or self.config.top_k or len(documents),
                truncation=self.truncation,
            )

            # Create reranked results
            reranked_docs = []
            for result in response.results:
                original_doc = documents[result.index].copy()
                original_doc["rerank_score"] = result.relevance_score
                reranked_docs.append(original_doc)

            return reranked_docs

        except Exception:
            # Fallback to original order if reranking fails
            for doc in documents:
                doc["rerank_score"] = 0.0
            return documents[:top_k] if top_k else documents
