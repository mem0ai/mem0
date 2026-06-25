"""
Scoring utilities for hybrid retrieval.

Provides:
- **BM25 normalization**: Sigmoid normalization of raw BM25 scores to [0, 1].
- **BM25 parameter selection**: Query-length-adaptive sigmoid parameters.
- **Additive scoring**: Combined scoring with semantic + BM25 + entity boost.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone
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


def calculate_decay_multiplier(updated_at_str: Optional[str]) -> float:
    """Calculate the decay multiplier for a memory based on its last updated time.
    
    Args:
        updated_at_str: ISO format timestamp string
        
    Returns:
        Scaling factor in range [0.3, 1.5]
    """
    if not updated_at_str:
        return 1.0
        
    try:
        updated_at = datetime.fromisoformat(updated_at_str.replace("Z", "+00:00"))
    except ValueError:
        return 1.0

    now = datetime.now(timezone.utc)
    age_in_days = (now - updated_at).total_seconds() / 86400.0
    
    if age_in_days < 0:
        age_in_days = 0.0

    # Exponential decay mapping age to [0.3, 1.5]
    # base = 0.3, max = 1.5, amplitude = 1.2
    # at day 0: 0.3 + 1.2 = 1.5
    # at day 7: 0.3 + 1.2 * exp(-0.15 * 7) ~ 0.72
    multiplier = 0.3 + 1.2 * math.exp(-0.15 * age_in_days)
    return max(0.3, min(1.5, multiplier))


ENTITY_BOOST_WEIGHT = 0.5


def score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool = False,
    decay: bool = False,
) -> List[Dict[str, Any]]:
    """Score candidates additively and return top-k results.

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

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
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

        if decay:
            payload = result.get("payload") or {}
            # Fallback to created_at if updated_at is missing
            updated_at = payload.get("updated_at") or payload.get("created_at")
            decay_multiplier = calculate_decay_multiplier(updated_at)
            
            # Apply multiplier
            scored_result["score"] = combined * decay_multiplier
            
            if explain:
                scored_result["score_details"] = {
                    "semantic_score": semantic_score,
                    "bm25_score": bm25_score,
                    "entity_boost": entity_boost,
                    "raw_score": raw_combined,
                    "max_possible_score": max_possible,
                    "combined_score": combined,
                    "decay_multiplier": decay_multiplier,
                    "final_score": min(scored_result["score"], 1.0),
                    "threshold": threshold,
                }
        else:
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
    scored = scored[:top_k]
    
    # Clamp final scores to [0, 1]
    for s in scored:
        s["score"] = min(s["score"], 1.0)
        
    return scored
