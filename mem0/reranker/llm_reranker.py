import re
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

        # Honor custom scoring_prompt from config if provided
        custom_prompt = getattr(self.config, 'scoring_prompt', None)
        if custom_prompt:
            import warnings
            warnings.warn(
                "LLMRerankerConfig.scoring_prompt is deprecated and will be removed in a future version. "
                "The prompt is now used as the system message.",
                DeprecationWarning,
                stacklevel=2,
            )
            self._system_prompt = custom_prompt
        else:
            self._system_prompt = self._SYSTEM_PROMPT

    _SYSTEM_PROMPT = (
        "You are a relevance scoring assistant. "
        "Given a query and a document, score how relevant the document is to the query.\n\n"
        "Score the relevance on a scale from 0.0 to 1.0, where:\n"
        "- 1.0 = Perfectly relevant and directly answers the query\n"
        "- 0.8-0.9 = Highly relevant with good information\n"
        "- 0.6-0.7 = Moderately relevant with some useful information\n"
        "- 0.4-0.5 = Slightly relevant with limited useful information\n"
        "- 0.0-0.3 = Not relevant or no useful information\n\n"
        "Respond with only a single numerical score between 0.0 and 1.0. "
        "Do not include any explanation or additional text."
    )

    # Maximum character length for query and document inputs to prevent prompt flooding.
    _MAX_INPUT_LEN = 4000

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
        
        scored_docs = []
        
        for doc in documents:
            # Extract text content
            if 'memory' in doc:
                doc_text = doc['memory']
            elif 'text' in doc:
                doc_text = doc['text']  
            elif 'content' in doc:
                doc_text = doc['content']
            else:
                doc_text = str(doc)
            
            try:
                # Truncate inputs to prevent prompt flooding, then send as separate
                # system/user messages so instructions cannot be overridden by user data.
                safe_query = query[: self._MAX_INPUT_LEN]
                safe_doc = doc_text[: self._MAX_INPUT_LEN]
                user_message = f"Query: {safe_query}\n\nDocument: {safe_doc}"

                response = self.llm.generate_response(
                    messages=[
                        {"role": "system", "content": self._system_prompt},
                        {"role": "user", "content": user_message},
                    ]
                )
                
                # Extract score from response
                score = self._extract_score(response)
                
                # Create scored document
                scored_doc = doc.copy()
                scored_doc['rerank_score'] = score
                scored_docs.append(scored_doc)

            except Exception:
                # Fallback: assign neutral score if scoring fails
                scored_doc = doc.copy()
                scored_doc['rerank_score'] = 0.5
                scored_docs.append(scored_doc)
        
        # Sort by relevance score in descending order
        scored_docs.sort(key=lambda x: x['rerank_score'], reverse=True)
        
        # Apply top_k limit
        if top_k:
            scored_docs = scored_docs[:top_k]
        elif self.config.top_k:
            scored_docs = scored_docs[:self.config.top_k]
            
        return scored_docs