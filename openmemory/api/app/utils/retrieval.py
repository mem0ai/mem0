"""
Advanced retrieval pipeline for OpenMemory search.

OpenMemory's MCP server originally hand-rolled retrieval as a single dense
``vector_store.search`` call, bypassing the hybrid-search and reranking the mem0
SDK already ships. This module restores them as a proper RAG pipeline:

1. Hybrid candidate generation
   - Dense: semantic vector search (embedding similarity).
   - Sparse: BM25 keyword search (exact-term recall) when the Qdrant collection
     has the ``bm25`` slot and the encoder is available. Degrades silently to
     dense-only otherwise (e.g. pre-v3 collections), so it is safe for
     forward-only deployments.
2. Reciprocal Rank Fusion (RRF) merges the two ranked lists. RRF is rank-based,
   so it needs no score normalization between the (incomparable) cosine and BM25
   scales — the standard robust choice for hybrid search.
3. Reranking: a cross-encoder / hosted reranker (Cohere or LLM) reorders the
   fused candidates by true query-document relevance — the single largest
   accuracy gain. Applied only if a reranker is configured on the client.

ACL is intentionally NOT applied here; the caller resolves the user's accessible
set once (see ``app.utils.acl``) and filters the small candidate list, which
avoids the per-memory N+1 the previous implementation incurred.
"""

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# mem0 indexes BM25 on lemmatized text, so the sparse query must be lemmatized
# the same way or keyword recall silently degrades. Falls back to identity if
# mem0's lemmatizer (spaCy) is unavailable.
try:
    from mem0.utils.lemmatization import lemmatize_for_bm25
except Exception:  # pragma: no cover - defensive
    def lemmatize_for_bm25(text: str) -> str:
        return text

# RRF dampening constant. 60 is the value from the original RRF paper and the de
# facto default across search engines; larger => flatter contribution by rank.
_RRF_K = 60


def _payload_of(hit: Any) -> Dict[str, Any]:
    return getattr(hit, "payload", None) or {}


def _id_of(hit: Any) -> Optional[str]:
    hid = getattr(hit, "id", None)
    return str(hid) if hid is not None else None


def _hit_to_doc(hit: Any, fused_score: float) -> Dict[str, Any]:
    """Normalize a Qdrant hit into the result dict shape the MCP layer returns."""
    payload = _payload_of(hit)
    return {
        "id": _id_of(hit),
        "memory": payload.get("data"),
        "hash": payload.get("hash"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "score": fused_score,
    }


def reciprocal_rank_fusion(
    ranked_lists: List[List[Any]],
    k: int = _RRF_K,
) -> List[Tuple[str, Any, float]]:
    """Fuse multiple ranked hit lists into one, by RRF.

    Args:
        ranked_lists: Each inner list is hits ordered best-first.
        k: RRF dampening constant.

    Returns:
        List of ``(id, hit, fused_score)`` ordered best-first. The first hit seen
        for a given id is kept as the representative (payloads are identical
        across dense/sparse for the same point).
    """
    scores: Dict[str, float] = {}
    reps: Dict[str, Any] = {}
    for ranked in ranked_lists:
        if not ranked:
            continue
        for rank, hit in enumerate(ranked):
            hid = _id_of(hit)
            if hid is None:
                continue
            scores[hid] = scores.get(hid, 0.0) + 1.0 / (k + rank)
            reps.setdefault(hid, hit)
    fused = [(hid, reps[hid], score) for hid, score in scores.items()]
    fused.sort(key=lambda t: t[2], reverse=True)
    return fused


def hybrid_search(
    memory_client: Any,
    query: str,
    user_id: str,
    *,
    candidate_k: int = 30,
    reranker: Any = None,
    embedding: Optional[List[float]] = None,
) -> Tuple[List[Dict[str, Any]], Optional[List[float]]]:
    """Run the dense + sparse + fusion + rerank pipeline.

    Returns the FULL reranked candidate pool (up to ``candidate_k``) — it does NOT
    truncate to a final page size. The caller applies ACL + state filtering to
    this pool and truncates afterwards, so ACL/state-restricted apps still get a
    full page instead of a pre-truncated remnant.

    Args:
        memory_client: Initialized mem0 ``Memory`` client.
        query: Search query text.
        user_id: Entity id; pushed into the Qdrant payload filter.
        candidate_k: How many candidates each retriever fetches before fusion,
            and the size of the returned pool.
        reranker: A reranker exposing ``rerank(query, docs, top_k)``. If None,
            falls back to ``memory_client.reranker``; if that is also None, the
            fused RRF order is returned.
        embedding: Precomputed query embedding (reused from cache path) to avoid
            a redundant embedding call. Computed here if not provided.

    Returns:
        ``(results, embedding)`` — results are best-first result dicts; embedding
        is returned so the caller can reuse it for the semantic cache.
    """
    filters = {"user_id": user_id}
    vector_store = memory_client.vector_store

    if embedding is None:
        embedding = memory_client.embedding_model.embed(query, "search")

    # Dense (semantic) retrieval.
    try:
        dense_hits = vector_store.search(
            query=query,
            vectors=embedding,
            top_k=candidate_k,
            filters=filters,
        )
    except Exception as e:
        logger.warning(f"Dense search failed: {e}")
        dense_hits = []

    # Sparse (BM25 keyword) retrieval — optional; None when unavailable. The
    # query is lemmatized to match how mem0 built the BM25 index at write time.
    sparse_hits = []
    keyword_search = getattr(vector_store, "keyword_search", None)
    if callable(keyword_search):
        try:
            result = keyword_search(lemmatize_for_bm25(query), top_k=candidate_k, filters=filters)
            if result:
                sparse_hits = result
        except Exception as e:
            logger.debug(f"BM25 keyword search unavailable: {e}")

    fused = reciprocal_rank_fusion([dense_hits, sparse_hits])
    candidates = [_hit_to_doc(hit, score) for _, hit, score in fused]

    # Rerank the WHOLE fused pool (top_k=None) so the over-fetch is not discarded
    # before ACL/state filtering downstream.
    if reranker is None:
        reranker = getattr(memory_client, "reranker", None)
    if reranker is not None and candidates:
        try:
            reranked = reranker.rerank(query, candidates, None)
            # Surface the rerank score as the primary score for the caller.
            for doc in reranked:
                if "rerank_score" in doc:
                    doc["score"] = doc["rerank_score"]
            candidates = reranked
        except Exception as e:
            logger.warning(f"Reranking failed, using fused order: {e}")

    return candidates[:candidate_k], embedding
