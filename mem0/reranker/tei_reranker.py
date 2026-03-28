import logging
from typing import List, Dict, Any, Union

import requests

from mem0.reranker.base import BaseReranker
from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.tei import TEIRerankerConfig

logger = logging.getLogger(__name__)


class TEIReranker(BaseReranker):
    """TEI (Text Embeddings Inference) HTTP-based reranker implementation."""

    def __init__(self, config: Union[BaseRerankerConfig, TEIRerankerConfig, Dict]):
        """
        Initialize TEI reranker.

        Args:
            config: Configuration object with reranker parameters
        """
        if isinstance(config, dict):
            config = TEIRerankerConfig(**config)
        elif isinstance(config, BaseRerankerConfig) and not isinstance(config, TEIRerankerConfig):
            config = TEIRerankerConfig(
                base_url=getattr(config, "base_url", "http://localhost:8184"),
                top_k=getattr(config, "top_k", None),
            )

        self.config = config
        self.rerank_url = f"{self.config.base_url.rstrip('/')}/rerank"

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents by calling the TEI /rerank endpoint.

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
            response = requests.post(
                self.rerank_url,
                json={"query": query, "texts": doc_texts},
                timeout=self.config.timeout,
            )
            response.raise_for_status()
            results = response.json()

            # Build index -> score mapping
            score_map = {item["index"]: item["score"] for item in results}

            # Combine documents with scores and sort descending
            doc_score_pairs = []
            for i, doc in enumerate(documents):
                score = score_map.get(i, 0.0)
                doc_score_pairs.append((doc, score))

            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)

            # Apply top_k limit
            final_top_k = top_k or self.config.top_k
            if final_top_k:
                doc_score_pairs = doc_score_pairs[:final_top_k]

            # Create reranked results
            reranked_docs = []
            for doc, score in doc_score_pairs:
                reranked_doc = doc.copy()
                reranked_doc["rerank_score"] = float(score)
                reranked_docs.append(reranked_doc)

            return reranked_docs

        except Exception as e:
            logger.warning("TEI reranker failed, returning original order: %s", e)
            fallback = [dict(d, rerank_score=0.0) for d in documents]
            final_top_k = top_k or self.config.top_k
            return fallback[:final_top_k] if final_top_k else fallback
