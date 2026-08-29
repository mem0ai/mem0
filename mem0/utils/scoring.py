"""
Scoring utilities for hybrid retrieval.

Provides:
- **BM25 normalization**: Sigmoid normalization of raw BM25 scores to [0, 1].
- **BM25 parameter selection**: Query-length-adaptive sigmoid parameters.
- **Blended scoring**: Fixed-weight combination of semantic, BM25, and entity.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


def get_bm25_params(query: str, *, lemmatized: Optional[str] = None) -> tuple:
    """Get BM25 sigmoid parameters based on query length.

    Longer queries tend to have higher raw BM25 scores, so we adjust
    the sigmoid midpoint and steepness accordingly.

    Returns:
        (midpoint, steepness) for sigmoid normalization.
    """
    if lemmatized is None:
        from mem0.utils.lemmatization import lemmatize_for_bm25

        lemmatized = lemmatize_for_bm25(query)
    num_terms = len(lemmatized.split()) if lemmatized else 1

    if num_terms <= 3:
        return 5.0, 0.7
    elif num_terms <= 6:
        return 7.0, 0.6
    elif num_terms <= 9:
        return 9.0, 0.5
    elif num_terms <= 15:
        return 10.0, 0.5
    else:
        return 12.0, 0.5


def normalize_bm25(raw_score: float, midpoint: float, steepness: float) -> float:
    """Normalize BM25 score to [0, 1] using logistic sigmoid.

    Args:
        raw_score: Raw BM25 score (unbounded, typically 0-20+).
        midpoint: Score at which sigmoid outputs 0.5.
        steepness: Controls how quickly sigmoid transitions.

    Returns:
        Normalized score in range [0, 1].
    """
    return 1.0 / (1.0 + math.exp(-steepness * (raw_score - midpoint)))


ENTITY_BOOST_WEIGHT = 0.5

# Fixed blend weights, summing to 1.0 so a combined score is always in [0, 1].
# NOTE: these must not vary with which signals a batch happened to produce. A
# divisor chosen from the batch makes a memory's score depend on what other
# memories matched, which is invisible in ranking and wrong for any caller
# thresholding on the number.
W_SEMANTIC = 0.6
W_BM25 = 0.3
W_ENTITY = 0.1


def score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool = False,
) -> List[Dict[str, Any]]:
    """Score candidates by a fixed weighted blend and return top-k results.

    For each candidate:
        semantic_score is taken from the result's score field.
        combined = W_SEMANTIC * semantic + W_BM25 * bm25 + W_ENTITY * entity

    The weights are constant and sum to 1.0, so a combined score is always in
    [0, 1] and comparable across queries. A signal the candidate does not have
    simply contributes 0.

    Threshold gates the semantic score BEFORE combining -- candidates
    below the threshold are excluded even if BM25/entity would boost them.
    Candidates flagged ``keyword_only`` have no measured semantic score and
    are gated on their BM25 score instead.

    Args:
        semantic_results: Candidate memories from vector search.
        bm25_scores: Normalized keyword scores keyed by memory ID.
        entity_boosts: Entity-link boosts keyed by memory ID.
        threshold: Minimum semantic score required before hybrid scoring.
        top_k: Maximum number of results to return.
        explain: Include score_details in each result when true.

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
    scored: List[Dict[str, Any]] = []

    for result in semantic_results:
        mem_id = result.get("id")
        if mem_id is None:
            continue

        mem_id_str = str(mem_id)
        bm25_score = bm25_scores.get(mem_id_str, 0.0)
        entity_boost = entity_boosts.get(mem_id_str, 0.0)

        semantic_score = result.get("score") or 0.0
        if result.get("keyword_only"):
            # No semantic score was ever measured for this candidate, so the
            # semantic threshold cannot speak to it. Gate on the one signal
            # we do have.
            if bm25_score < threshold:
                continue
        elif semantic_score < threshold:
            continue

        # Entity boosts arrive pre-scaled to [0, ENTITY_BOOST_WEIGHT]; rescale
        # so W_ENTITY is the only thing deciding how much entities count.
        entity_signal = entity_boost / ENTITY_BOOST_WEIGHT

        weighted = W_SEMANTIC * semantic_score + W_BM25 * bm25_score + W_ENTITY * entity_signal
        if result.get("keyword_only"):
            # Renormalize over the signals this candidate could actually earn.
            # NOTE: the divisor comes from the candidate's own missing data, not
            # from what the rest of the batch produced, so scores stay
            # comparable. Charging it the semantic weight instead would cap a
            # perfect term match at W_BM25 and bury it under any mediocre
            # semantic hit.
            weighted /= W_BM25 + W_ENTITY

        combined = min(weighted, 1.0)

        scored_result = {
            "id": mem_id_str,
            "score": combined,
            "payload": result.get("payload"),
        }
        if explain:
            scored_result["score_details"] = {
                "semantic_score": semantic_score,
                "bm25_score": bm25_score,
                "entity_boost": entity_boost,
                "weights": {"semantic": W_SEMANTIC, "bm25": W_BM25, "entity": W_ENTITY},
                "final_score": combined,
                "threshold": threshold,
            }
        scored.append(scored_result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
