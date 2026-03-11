import re
from typing import List, Dict, Any, Union

from mem0.reranker.base import BaseReranker
from mem0.utils.factory import LlmFactory
from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.llm import LLMRerankerConfig
import concurrent.futures


class LLMReranker(BaseReranker):
    """LLM-based reranker implementation."""

    def __init__(self, config: Union[BaseRerankerConfig, LLMRerankerConfig, Dict]):
        """
        Initialize LLM reranker.

        Args:
            config: Configuration object with reranker parameters
        """
        # Convert to LLMRerankerConfig if needed
        if isinstance(config, dict):
            config = LLMRerankerConfig(**config)
        elif isinstance(config, BaseRerankerConfig) and not isinstance(config, LLMRerankerConfig):
            # Convert BaseRerankerConfig to LLMRerankerConfig with defaults
            config = LLMRerankerConfig(
                provider=getattr(config, 'provider', 'openai'),
                model=getattr(config, 'model', 'gpt-4o-mini'),
                api_key=getattr(config, 'api_key', None),
                top_k=getattr(config, 'top_k', None),
                temperature=0.0,  # Default for reranking
                max_tokens=100,   # Default for reranking
            )

        self.config = config

        # Create LLM configuration for the factory
        llm_config = {
            "model": self.config.model,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        # Add API key if provided
        if self.config.api_key:
            llm_config["api_key"] = self.config.api_key

        # Initialize LLM using the factory
        self.llm = LlmFactory.create(self.config.provider, llm_config)

        # Default scoring prompt
        self.scoring_prompt = getattr(self.config, 'scoring_prompt', None) or self._get_default_prompt()
        
    def _get_default_prompt(self) -> str:
        """Get the default scoring prompt template."""
        return """You are a relevance scoring assistant. Given a query and a document, you need to score how relevant the document is to the query.

Score the relevance on a scale from 0.0 to 1.0, where:
- 1.0 = Perfectly relevant and directly answers the query
- 0.8-0.9 = Highly relevant with good information
- 0.6-0.7 = Moderately relevant with some useful information  
- 0.4-0.5 = Slightly relevant with limited useful information
- 0.0-0.3 = Not relevant or no useful information

Query: "{query}"
Document: "{document}"

Provide only a single numerical score between 0.0 and 1.0. Do not include any explanation or additional text."""

    def _extract_score(self, response_text: str) -> float:
        """Extract numerical score from LLM response."""
        # Look for decimal numbers between 0.0 and 1.0
        pattern = r'\b([01](?:\.\d+)?)\b'
        matches = re.findall(pattern, response_text)
        
        if matches:
            score = float(matches[0])
            return min(max(score, 0.0), 1.0)  # Clamp between 0.0 and 1.0
        
        # Fallback: return 0.5 if no valid score found
        return 0.5
    
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using LLM scoring.

        Args:
            query: The search query
            documents: List of documents to rerank
            top_k: Number of top documents to return

        Returns:
            List of reranked documents with rerank_score
        """
        if not documents:
            return documents

        effective_top_k = top_k or self.config.top_k
        max_concurrency = getattr(self.config, "max_concurrency", None)

        def _doc_to_text(doc: Dict[str, Any]) -> str:
            if "memory" in doc:
                return doc["memory"]
            if "text" in doc:
                return doc["text"]
            if "content" in doc:
                return doc["content"]
            return str(doc)

        def _score_doc(doc_text: str) -> float:
            prompt = self.scoring_prompt.format(query=query, document=doc_text)
            response = self.llm.generate_response(messages=[{"role": "user", "content": prompt}])
            return self._extract_score(response)

        # Sequential path (default / backwards compatible)
        if not max_concurrency or max_concurrency <= 1 or len(documents) == 1:
            scored_docs: List[Dict[str, Any]] = []
            for doc in documents:
                try:
                    score = _score_doc(_doc_to_text(doc))
                except Exception:
                    score = 0.5

                scored_doc = doc.copy()
                scored_doc["rerank_score"] = score
                scored_docs.append(scored_doc)

            scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
            if effective_top_k:
                scored_docs = scored_docs[:effective_top_k]
            return scored_docs

        # Concurrent path (threaded, concurrency-limited)
        max_workers = min(int(max_concurrency), len(documents))

        def _score_single(idx: int, doc: Dict[str, Any]) -> tuple[int, float]:
            try:
                score = _score_doc(_doc_to_text(doc))
            except Exception:
                score = 0.5
            return idx, score

        scores: Dict[int, float] = {}
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(_score_single, idx, doc) for idx, doc in enumerate(documents)]
            for future in concurrent.futures.as_completed(futures):
                idx, score = future.result()
                scores[idx] = score

        scored_docs: List[Dict[str, Any]] = []
        for idx, doc in enumerate(documents):
            scored_doc = doc.copy()
            scored_doc["rerank_score"] = scores.get(idx, 0.5)
            scored_docs.append(scored_doc)

        scored_docs.sort(key=lambda x: x["rerank_score"], reverse=True)
        if effective_top_k:
            scored_docs = scored_docs[:effective_top_k]
        return scored_docs