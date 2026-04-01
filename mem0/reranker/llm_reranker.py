import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Union

from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.llm import LLMRerankerConfig
from mem0.reranker.base import BaseReranker
from mem0.utils.factory import LlmFactory


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

        # If a nested ``llm`` dict is provided (e.g. for non-OpenAI providers
        # like Ollama that need provider-specific fields such as
        # ``ollama_base_url``), use it to configure the LLM factory.
        if self.config.llm:
            nested = self.config.llm
            llm_provider = nested.get("provider", self.config.provider)
            llm_config: dict = dict(nested.get("config") or {})
            llm_config.setdefault("model", self.config.model)
            llm_config.setdefault("temperature", self.config.temperature)
            llm_config.setdefault("max_tokens", self.config.max_tokens)
            if self.config.api_key:
                llm_config.setdefault("api_key", self.config.api_key)
        else:
            llm_provider = self.config.provider
            llm_config = {
                "model": self.config.model,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            if self.config.api_key:
                llm_config["api_key"] = self.config.api_key

        # Initialize LLM using the factory
        self.llm = LlmFactory.create(llm_provider, llm_config)

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

    def _score_document(self, query: str, doc: Dict[str, Any]) -> Dict[str, Any]:
        """Score a single document against the query.

        Returns the document dict (copy) with a ``rerank_score`` field added.
        Falls back to 0.5 on any LLM error so the pipeline never hard-fails.
        """
        if 'memory' in doc:
            doc_text = doc['memory']
        elif 'text' in doc:
            doc_text = doc['text']
        elif 'content' in doc:
            doc_text = doc['content']
        else:
            doc_text = str(doc)

        try:
            prompt = self.scoring_prompt.format(query=query, document=doc_text)
            response = self.llm.generate_response(
                messages=[{"role": "user", "content": prompt}]
            )
            score = self._extract_score(response)
        except Exception:
            score = 0.5

        scored_doc = doc.copy()
        scored_doc['rerank_score'] = score
        return scored_doc

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using LLM scoring.

        Documents are scored in parallel when ``max_workers > 1``, reducing
        latency proportionally to the number of workers.

        Args:
            query: The search query.
            documents: List of documents to rerank, each with a 'memory',
                'text', or 'content' field.
            top_k: Number of top documents to return. Falls back to
                ``config.top_k`` when not provided.

        Returns:
            List of reranked documents sorted by ``rerank_score`` descending,
            with the score added to each document dict.
        """
        if not documents:
            return documents

        max_workers = min(self.config.max_workers, len(documents))

        if max_workers > 1:
            # Parallel scoring — submit all documents concurrently
            scored_docs: List[Dict[str, Any]] = [None] * len(documents)
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_idx = {
                    executor.submit(self._score_document, query, doc): idx
                    for idx, doc in enumerate(documents)
                }
                for future in as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    try:
                        scored_docs[idx] = future.result()
                    except Exception:
                        fallback = documents[idx].copy()
                        fallback['rerank_score'] = 0.5
                        scored_docs[idx] = fallback
        else:
            # Sequential scoring (default, max_workers=1)
            scored_docs = [self._score_document(query, doc) for doc in documents]

        # Sort by relevance score descending
        scored_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

        # Apply top_k limit
        effective_top_k = top_k or self.config.top_k
        if effective_top_k:
            scored_docs = scored_docs[:effective_top_k]

        return scored_docs
