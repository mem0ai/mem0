"""
Self-hostable reranker for OpenMemory search.

Reranking the fused candidate list with a cross-encoder is the single largest
accuracy lever in the pipeline. The default is a local FastEmbed ONNX
cross-encoder — no external SaaS, no torch, and the FastEmbed runtime is already
resident because the BM25 sparse path uses it. This honors the "self-hostable
first" priority while keeping latency low (in-process, no network hop).

Provider selection via RERANKER_PROVIDER (default 'fastembed'):
  - fastembed         : local ONNX cross-encoder (DEFAULT, self-hosted)
  - none/off/disabled : no rerank (hybrid RRF order only)
  - cohere            : external SaaS (opt-in; requires `pip install cohere` + COHERE_API_KEY)
  - llm / llm_reranker: per-candidate LLM scoring (opt-in; N calls/search)
  - sentence_transformer / huggingface / zero_entropy: mem0 built-ins (extra deps)

The returned object exposes ``rerank(query, documents, top_k)`` matching mem0's
BaseReranker contract: documents are dicts with a 'memory' field; results are
copies with an added 'rerank_score', sorted descending.
"""

import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = os.environ.get("RERANK_MODEL", "Xenova/ms-marco-MiniLM-L-6-v2")
_RERANK_ENABLED = os.environ.get("OPENMEMORY_RERANK_ENABLED", "true").lower() == "true"

_reranker_instance = "uninitialized"  # sentinel distinct from a resolved None
_reranker_lock = threading.Lock()


def _doc_text(doc: Dict[str, Any]) -> str:
    for key in ("memory", "text", "content"):
        if doc.get(key):
            return doc[key]
    return ""


class FastEmbedReranker:
    """Local ONNX cross-encoder reranker (self-hosted, via FastEmbed)."""

    def __init__(self, model_name: str = _DEFAULT_MODEL):
        self.model_name = model_name
        self._encoder = None
        self._encoder_lock = threading.Lock()

    def _get_encoder(self):
        # Lazy: the model (~80MB ONNX) loads on first use, not at import.
        if self._encoder is None:
            with self._encoder_lock:
                if self._encoder is None:
                    from fastembed.rerank.cross_encoder import TextCrossEncoder

                    self._encoder = TextCrossEncoder(model_name=self.model_name)
        return self._encoder

    def rerank(self, query: str, documents: List[Dict[str, Any]], top_k: Optional[int] = None) -> List[Dict[str, Any]]:
        if not documents:
            return documents
        texts = [_doc_text(d) for d in documents]
        # FastEmbed returns relevance logits (higher = more relevant), aligned to
        # the input order. Can be negative; we only need the ordering.
        scores = list(self._get_encoder().rerank(query, texts))
        scored = []
        for doc, score in zip(documents, scores):
            new_doc = dict(doc)
            new_doc["rerank_score"] = float(score)
            scored.append(new_doc)
        scored.sort(key=lambda d: d["rerank_score"], reverse=True)
        return scored[:top_k] if top_k else scored


def _build_reranker():
    """Construct the configured reranker, or None to disable. Never raises."""
    if not _RERANK_ENABLED:
        return None

    provider = os.environ.get("RERANKER_PROVIDER", "fastembed").lower()

    if provider in ("none", "off", "disabled"):
        return None

    if provider == "fastembed":
        try:
            import fastembed.rerank.cross_encoder  # noqa: F401  (verify availability)

            return FastEmbedReranker()
        except Exception as e:
            logger.warning(
                f"FastEmbed reranker unavailable ({e}); falling back to no rerank "
                f"(hybrid RRF order). Install fastembed to enable self-hosted reranking."
            )
            return None

    # Opt-in providers handled by mem0's RerankerFactory (lazy imports inside mem0).
    try:
        from mem0.utils.factory import RerankerFactory

        if provider == "cohere":
            config = {
                "api_key": os.environ.get("COHERE_API_KEY"),
                "model": os.environ.get("COHERE_RERANK_MODEL", "rerank-v3.5"),
            }
            return RerankerFactory.create("cohere", config)

        if provider in ("llm", "llm_reranker"):
            config = {
                "provider": os.environ.get("RERANK_LLM_PROVIDER", "openai"),
                "model": os.environ.get("RERANK_LLM_MODEL", "gpt-4o-mini"),
                "api_key": os.environ.get("OPENAI_API_KEY"),
            }
            return RerankerFactory.create("llm_reranker", config)

        # Other mem0 providers (sentence_transformer, huggingface, zero_entropy).
        return RerankerFactory.create(provider, {})
    except Exception as e:
        logger.warning(f"Reranker provider '{provider}' unavailable ({e}); disabling rerank.")
        return None


def get_reranker():
    """Return the process-wide reranker singleton (or None if disabled)."""
    global _reranker_instance
    if _reranker_instance != "uninitialized":
        return _reranker_instance
    with _reranker_lock:
        if _reranker_instance == "uninitialized":
            _reranker_instance = _build_reranker()
            if _reranker_instance is not None:
                logger.info(f"Reranker enabled: {type(_reranker_instance).__name__}")
            else:
                logger.info("Reranker disabled (hybrid RRF order only)")
    return _reranker_instance


def reset_reranker() -> None:
    """Reset the singleton (used by tests)."""
    global _reranker_instance
    with _reranker_lock:
        _reranker_instance = "uninitialized"
