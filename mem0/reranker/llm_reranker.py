import os
import re
from typing import List, Dict, Any, Optional

from mem0.reranker.base import BaseReranker
from mem0.utils.factory import LlmFactory


class LLMReranker(BaseReranker):
    """LLM-based reranker implementation."""
    
    def __init__(self, config):
        """
        Initialize LLM reranker.
        
        Args:
            config: LLMRerankerConfig object with configuration parameters
        """
        self.config = config
        
        # Create LLM configuration for the factory
        llm_config = {
            "model": config.model,
            "temperature": config.temperature,
            "max_tokens": config.max_tokens,
        }
        
        # Add API key if provided
        if config.api_key:
            llm_config["api_key"] = config.api_key
        
        # Initialize LLM using the factory
        self.llm = LlmFactory.create(config.provider, llm_config)
        
        # Default scoring prompt
        self.scoring_prompt = config.scoring_prompt or self._get_default_prompt()
        
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
                # Generate scoring prompt
                prompt = self.scoring_prompt.format(query=query, document=doc_text)
                
                # Get LLM response
                response = self.llm.generate_response(
                    messages=[{"role": "user", "content": prompt}]
                )
                
                # Extract score from response
                score = self._extract_score(response)
                
                # Create scored document
                scored_doc = doc.copy()
                scored_doc['rerank_score'] = score
                scored_docs.append(scored_doc)
                
            except Exception as e:
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