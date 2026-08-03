import logging
import os
from typing import Any, Dict, List

import httpx

from mem0.reranker.base import BaseReranker

logger = logging.getLogger(__name__)


class OpenAICompatibleReranker(BaseReranker):
    """
    Reranker for any service exposing an OpenAI/Cohere-compatible ``/rerank`` endpoint.

    The endpoint is expected to accept::

        POST {base_url}/rerank
        Authorization: Bearer {api_key}
        {"model": "...", "query": "...", "documents": ["...", "..."], "top_n": N}

    and respond with a Cohere/Jina-style payload::

        {"results": [{"index": 0, "relevance_score": 0.9}, ...]}

    This covers self-hosted ``bge-reranker``, Jina, Voyage, SiliconFlow, Together,
    vLLM-hosted rerankers and internal OpenAI-compatible gateways.
    """

    def __init__(self, config):
        """
        Initialize the OpenAI-compatible reranker.

        Args:
            config: OpenAICompatibleRerankerConfig object with configuration parameters
        """
        self.config = config

        base_url = getattr(config, "base_url", None) or os.getenv("RERANKER_BASE_URL")
        if not base_url:
            raise ValueError(
                "base_url is required for OpenAICompatibleReranker. "
                "Set it in the reranker config or the RERANKER_BASE_URL environment variable."
            )
        self.base_url = base_url.rstrip("/")
        self.endpoint = f"{self.base_url}/rerank"

        self.api_key = config.api_key or os.getenv("RERANKER_API_KEY")
        self.model = config.model
        self.timeout = getattr(config, "timeout", 60.0)

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        extra_headers = getattr(config, "headers", None)
        if extra_headers:
            headers.update(extra_headers)
        self.headers = headers

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using an OpenAI/Cohere-compatible rerank endpoint.

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

        top_n = top_k or self.config.top_k or len(documents)
        payload = {
            "query": query,
            "documents": doc_texts,
            "top_n": top_n,
        }
        if self.model:
            payload["model"] = self.model

        try:
            response = httpx.post(self.endpoint, json=payload, headers=self.headers, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            # Accept both {"results": [...]} and a bare list of results.
            results = data.get("results", data) if isinstance(data, dict) else data

            # Create reranked results, mapping the returned index back onto the input docs.
            reranked_docs = []
            for result in results:
                index = result["index"]
                score = result.get("relevance_score", result.get("score", 0.0))
                original_doc = documents[index].copy()
                original_doc["rerank_score"] = score
                reranked_docs.append(original_doc)

            # Sort by relevance score in descending order
            reranked_docs.sort(key=lambda x: x["rerank_score"], reverse=True)

            # Apply top_k limit
            if top_k:
                reranked_docs = reranked_docs[:top_k]
            elif self.config.top_k:
                reranked_docs = reranked_docs[: self.config.top_k]

            return reranked_docs

        except Exception as e:
            logger.warning(f"OpenAI-compatible reranking failed, returning original order: {e}")
            # Fallback to original order if reranking fails
            for doc in documents:
                doc["rerank_score"] = 0.0
            return documents[:top_k] if top_k else documents
