from typing import List, Dict, Any, Union
import numpy as np

from mem0.reranker.base import BaseReranker
from mem0.configs.rerankers.base import BaseRerankerConfig
from mem0.configs.rerankers.huggingface import HuggingFaceRerankerConfig

try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class HuggingFaceReranker(BaseReranker):
    """HuggingFace Transformers based reranker implementation."""

    def __init__(self, config: Union[BaseRerankerConfig, HuggingFaceRerankerConfig, Dict]):
        """
        Initialize HuggingFace reranker.

        Args:
            config: Configuration object with reranker parameters
        """
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError("transformers package is required for HuggingFaceReranker. Install with: pip install transformers torch")

        # Convert to HuggingFaceRerankerConfig if needed
        if isinstance(config, dict):
            config = HuggingFaceRerankerConfig(**config)
        elif isinstance(config, BaseRerankerConfig) and not isinstance(config, HuggingFaceRerankerConfig):
            # Convert BaseRerankerConfig to HuggingFaceRerankerConfig with defaults
            config = HuggingFaceRerankerConfig(
                provider=getattr(config, 'provider', 'huggingface'),
                model=getattr(config, 'model', 'BAAI/bge-reranker-base'),
                api_key=getattr(config, 'api_key', None),
                top_k=getattr(config, 'top_k', None),
                device=None,  # Will auto-detect
                batch_size=32,  # Default
                max_length=512,  # Default
                normalize=True,  # Default
            )

        self.config = config

        # Set device
        if self.config.device is None:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
        else:
            self.device = self.config.device

        # Load model and tokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model)
        self.model = AutoModelForSequenceClassification.from_pretrained(self.config.model)
        self.model.to(self.device)
        self.model.eval()

    @staticmethod
    def _normalize_scores(scores: List[float]) -> List[float]:
        """Map raw cross-encoder logits into the [0, 1] range via a sigmoid.

        Cross-encoder rerankers (e.g. ``BAAI/bge-reranker-*``) emit unbounded
        logits; the documented way to obtain an interpretable [0, 1] relevance
        score is a per-document sigmoid (``1 / (1 + e^-x)``), which preserves the
        ranking order.

        This replaces the previous min-max scaling, which produced *set-relative*
        scores: the lowest-ranked document was always forced to 0.0, and a single
        document (or any set of tied scores) collapsed to 0.0 — wrongly reporting
        a result as completely irrelevant. Sigmoid scores each document on its own
        merit, so those cases are handled naturally.
        """
        if not scores:
            return []
        arr = np.asarray(scores, dtype=float)
        return (1.0 / (1.0 + np.exp(-arr))).tolist()

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
        """
        Rerank documents using HuggingFace cross-encoder model.

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
            scores = []

            # Process documents in batches
            for i in range(0, len(doc_texts), self.config.batch_size):
                batch_docs = doc_texts[i:i + self.config.batch_size]
                batch_pairs = [[query, doc] for doc in batch_docs]

                # Tokenize batch
                inputs = self.tokenizer(
                    batch_pairs,
                    padding=True,
                    truncation=True,
                    max_length=self.config.max_length,
                    return_tensors="pt"
                ).to(self.device)

                # Get scores
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    batch_scores = outputs.logits.squeeze(-1).cpu().numpy()

                    # Handle single item case
                    if batch_scores.ndim == 0:
                        batch_scores = [float(batch_scores)]
                    else:
                        batch_scores = batch_scores.tolist()

                    scores.extend(batch_scores)

            # Normalize scores if requested
            if self.config.normalize:
                scores = self._normalize_scores(scores)

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