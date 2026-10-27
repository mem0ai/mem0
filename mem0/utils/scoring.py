"""
Scoring utilities for hybrid retrieval.

Provides:
- **BM25 normalization**: Sigmoid normalization of raw BM25 scores to [0, 1].
- **BM25 parameter selection**: Query-length-adaptive sigmoid parameters.
- **Additive scoring**: Combined scoring with semantic + BM25 + entity boost.
- **Reciprocal rank fusion**: Optional equal-weight fusion of the same signals.
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


def score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool = False,
    fusion_strategy: str = "additive",
    rrf_k: int = 60,
) -> List[Dict[str, Any]]:
    """Score candidates with additive or reciprocal rank fusion and return top-k results.

    For each candidate:
        semantic_score is taken from the result's score field.
        combined = (semantic + bm25 + entity_boost) / max_possible

    Threshold gates the semantic score BEFORE combining -- candidates
    below the threshold are excluded even if BM25/entity would boost them.

    The divisor adapts based on which signals are active:
        - Semantic only: max_possible = 1.0
        - Semantic + BM25: max_possible = 2.0
        - Semantic + BM25 + entity: max_possible = 2.5
        - Semantic + entity (no BM25): max_possible = 1.5

    Args:
        semantic_results: Candidate memories from vector search.
        bm25_scores: Normalized keyword scores keyed by memory ID.
        entity_boosts: Entity-link boosts keyed by memory ID.
        threshold: Minimum semantic score required before hybrid scoring.
        top_k: Maximum number of results to return.
        explain: Include score_details in each result when true.
        fusion_strategy: "additive" (default) or "rrf". Both retain semantic eligibility checks.
        rrf_k: Positive integer rank offset for RRF. Not the number of results.

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
    if fusion_strategy not in ("additive", "rrf"):
        raise ValueError("fusion_strategy must be 'additive' or 'rrf'")
    if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or rrf_k <= 0:
        raise ValueError("rrf_k must be a positive integer")
    if fusion_strategy == "rrf":
        return _rrf_score_and_rank(semantic_results, bm25_scores, entity_boosts, threshold, top_k, explain, rrf_k)

    has_bm25 = bool(bm25_scores)
    has_entity = bool(entity_boosts)

    max_possible = 1.0
    if has_bm25:
        max_possible += 1.0
    if has_entity:
        max_possible += ENTITY_BOOST_WEIGHT

    scored: List[Dict[str, Any]] = []

    for result in semantic_results:
        mem_id = result.get("id")
        if mem_id is None:
            continue

        semantic_score = result.get("score") or 0.0
        if semantic_score < threshold:
            continue

        mem_id_str = str(mem_id)
        bm25_score = bm25_scores.get(mem_id_str, 0.0)
        entity_boost = entity_boosts.get(mem_id_str, 0.0)

        raw_combined = semantic_score + bm25_score + entity_boost
        combined = min(raw_combined / max_possible, 1.0)

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
                "raw_score": raw_combined,
                "max_possible_score": max_possible,
                "final_score": combined,
                "threshold": threshold,
            }
        scored.append(scored_result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _average_ranks(scores: Dict[str, float]) -> Dict[str, float]:
    """Rank descending, assigning each tie group its average one-based position."""
    ordered = sorted(scores, key=scores.get, reverse=True)
    ranks: Dict[str, float] = {}
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and scores[ordered[end]] == scores[ordered[start]]:
            end += 1
        rank = (start + 1 + end) / 2.0
        for memory_id in ordered[start:end]:
            ranks[memory_id] = rank
        start = end
    return ranks


def _rrf_score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool,
    rrf_k: int,
) -> List[Dict[str, Any]]:
    # Use exactly the existing semantic candidate pool and eligibility gate.
    eligible = [
        result
        for result in semantic_results
        if result.get("id") is not None
        and math.isfinite(result.get("score") or 0.0)
        and (result.get("score") or 0.0) >= threshold
    ]
    semantic_scores = {str(result["id"]): result.get("score") or 0.0 for result in eligible}
    keyword_scores = {
        memory_id: score
        for memory_id in semantic_scores
        if (score := bm25_scores.get(memory_id, 0.0)) > 0 and math.isfinite(score)
    }
    entity_scores = {
        memory_id: score
        for memory_id in semantic_scores
        if (score := entity_boosts.get(memory_id, 0.0)) > 0 and math.isfinite(score)
    }
    rank_maps = [_average_ranks(scores) for scores in (semantic_scores, keyword_scores, entity_scores)]
    active_channels = sum(bool(ranks) for ranks in rank_maps)
    scored: List[Dict[str, Any]] = []
    for result in eligible:
        memory_id = str(result["id"])
        ranks = [rank_map.get(memory_id) for rank_map in rank_maps]
        contributions = [1.0 / (rrf_k + rank) if rank is not None else 0.0 for rank in ranks]
        score = sum(contributions)
        entry = {"id": memory_id, "score": score, "payload": result.get("payload")}
        if explain:
            entry["score_details"] = {
                "semantic_score": semantic_scores[memory_id],
                "bm25_score": bm25_scores.get(memory_id, 0.0),
                "entity_boost": entity_boosts.get(memory_id, 0.0),
                "raw_score": score,
                "max_possible_score": active_channels / (rrf_k + 1),
                "final_score": score,
                "threshold": threshold,
                "fusion_strategy": "rrf",
                "rrf_k": rrf_k,
                "semantic_rank": ranks[0],
                "bm25_rank": ranks[1],
                "entity_rank": ranks[2],
                "semantic_contribution": contributions[0],
                "bm25_contribution": contributions[1],
                "entity_contribution": contributions[2],
            }
        scored.append(entry)
    scored.sort(key=lambda entry: entry["score"], reverse=True)
    return scored[:top_k]
