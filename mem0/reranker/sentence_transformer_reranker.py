import logging
from typing import List, Dict, Any, Union
import numpy as np

from mem0.reranker.base import BaseReranker
from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.sentence_transformer import SentenceTransformerRerankerConfig

logger = logging.getLogger(__name__)

try:
    from sentence_transformers import SentenceTransformer, CrossEncoder
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False


def _is_cross_encoder_model(model_name: str) -> bool:
    """Detect whether a model name refers to a cross-encoder model.

    Cross-encoder models are designed for reranking and should be loaded with
    ``CrossEncoder`` rather than ``SentenceTransformer``.  This function uses
    a simple heuristic: if the model name contains ``cross-encoder`` or
    ``reranker`` (case-insensitive), it is considered a cross-encoder model.
    """
    name_lower = model_name.lower()
    return "cross-encoder" in name_lower or "reranker" in name_lower


class SentenceTransformerReranker(BaseReranker):
    """Sentence Transformer based reranker implementation."""

    def __init__(self, config: Union[BaseRerankerConfig, SentenceTransformerRerankerConfig, Dict]):
        """
        Initialize Sentence Transformer reranker.

        Args:
            config: Configuration object with reranker parameters
        """
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError("sentence-transformers package is required for SentenceTransformerReranker. Install with: pip install sentence-transformers")

        # Convert to SentenceTransformerRerankerConfig if needed
        if isinstance(config, dict):
            config = SentenceTransformerRerankerConfig(**config)
        elif isinstance(config, BaseRerankerConfig) and not isinstance(config, SentenceTransformerRerankerConfig):
            # Convert BaseRerankerConfig to SentenceTransformerRerankerConfig with defaults
            config = SentenceTransformerRerankerConfig(
                provider=getattr(config, 'provider', 'sentence_transformer'),
                model=getattr(config, 'model', 'cross-encoder/ms-marco-MiniLM-L-6-v2'),
                api_key=getattr(config, 'api_key', None),
                top_k=getattr(config, 'top_k', None),
                device=None,  # Will auto-detect
                batch_size=32,  # Default
                show_progress_bar=False,  # Default
            )

        self.config = config

        # Use CrossEncoder for cross-encoder models, SentenceTransformer otherwise.
        # Cross-encoder models (e.g. "cross-encoder/ms-marco-MiniLM-L-6-v2") must
        # be loaded with CrossEncoder to produce meaningful relevance scores.
        # Loading them with SentenceTransformer causes a silent fallback to mean
        # pooling which yields all-zero rerank scores (see issue #4033).
        self._is_cross_encoder = _is_cross_encoder_model(self.config.model)
        if self._is_cross_encoder:
            self.model = CrossEncoder(self.config.model, device=self.config.device)
            logger.info("Loaded cross-encoder model '%s' with CrossEncoder", self.config.model)
        else:
            self.model = SentenceTransformer(self.config.model, device=self.config.device)
            logger.info("Loaded bi-encoder model '%s' with SentenceTransformer", self.config.model)
        
    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using sentence transformer cross-encoder.
        
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
            # Create query-document pairs
            pairs = [[query, doc_text] for doc_text in doc_texts]
            
            # Get similarity scores
            scores = self.model.predict(pairs)
            if isinstance(scores, np.ndarray):
                scores = scores.tolist()
            
            # Combine documents with scores
            doc_score_pairs = list(zip(documents, scores))
            
            # Sort by score (descending)
            doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
            
            # Apply top_k limit
            final_top_k = top_k or self.config.top_k
            if final_top_k:
                doc_score_pairs = doc_score_pairs[:final_top_k]
                
            # Create reranked results
            reranked_docs = []
            for doc, score in doc_score_pairs:
                reranked_doc = doc.copy()
                reranked_doc['rerank_score'] = float(score)
                reranked_docs.append(reranked_doc)
                
            return reranked_docs

        except Exception:
            # Fallback to original order if reranking fails
            for doc in documents:
                doc['rerank_score'] = 0.0
            final_top_k = top_k or self.config.top_k
            return documents[:final_top_k] if final_top_k else documents