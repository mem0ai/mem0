"""
Scoring utilities for hybrid retrieval.

Provides:
- **BM25 normalization**: Sigmoid normalization of raw BM25 scores to [0, 1].
- **BM25 parameter selection**: Query-length-adaptive sigmoid parameters.
- **Additive scoring**: Combined scoring with semantic + BM25 + entity boost (+ optional recency).
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


ENTITY_BOOST_WEIGHT = 0.5

# Default weight for the recency signal in score_and_rank. With semantic-only
# scoring, recency can contribute at most RECENCY_WEIGHT / (1 + RECENCY_WEIGHT)
# of the final score: enough to surface a newer memory in close calls, not
# enough to override a clearly more relevant one.
RECENCY_WEIGHT = 0.1


def _parse_timestamp(value: Any) -> Optional[float]:
    """Parse a timestamp value to epoch seconds.

    Accepts datetime objects, ISO-8601 strings (with or without timezone),
    and numeric epoch values. Naive datetimes/strings are assumed to be UTC.
    Returns None for missing or unparseable values.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return float(value)
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            # datetime.fromisoformat on Python 3.9 does not accept the "Z" suffix.
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    return None


def score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool = False,
    recency_weight: float = 0.0,
) -> List[Dict[str, Any]]:
    """Score candidates additively and return top-k results.

    For each candidate:
        semantic_score is taken from the result's score field.
        combined = (semantic + bm25 + entity_boost + recency_weight * recency) / max_possible

    Threshold gates the semantic score BEFORE combining -- candidates
    below the threshold are excluded even if BM25/entity would boost them.

    The recency signal is optional and off by default (recency_weight=0.0).
    When enabled (recency_weight > 0), each candidate's recency is derived
    from its payload's ``updated_at`` (falling back to ``created_at``) and
    min-max normalized across the candidates that pass the threshold, so the
    newest memory scores 1.0 and the oldest 0.0. Candidates without a
    parseable timestamp score 0.0. If no candidate carries a timestamp, the
    signal stays inactive and scores are identical to recency_weight=0.0.
    A non-positive recency_weight disables the signal.

    The divisor adapts based on which signals are active:
        - Semantic only: max_possible = 1.0
        - Semantic + BM25: max_possible = 2.0
        - Semantic + BM25 + entity: max_possible = 2.5
        - Semantic + entity (no BM25): max_possible = 1.5
        - Any of the above + recency: max_possible += recency_weight

    Args:
        semantic_results: Candidate memories from vector search.
        bm25_scores: Normalized keyword scores keyed by memory ID.
        entity_boosts: Entity-link boosts keyed by memory ID.
        threshold: Minimum semantic score required before hybrid scoring.
        top_k: Maximum number of results to return.
        explain: Include score_details in each result when true.
        recency_weight: Weight of the recency signal. 0.0 (default) disables it.

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
    has_bm25 = bool(bm25_scores)
    has_entity = bool(entity_boosts)

    # First pass: threshold gate on the semantic score (unchanged semantics).
    candidates: List[tuple] = []
    for result in semantic_results:
        mem_id = result.get("id")
        if mem_id is None:
            continue

        semantic_score = result.get("score") or 0.0
        if semantic_score < threshold:
            continue

        candidates.append((str(mem_id), semantic_score, result.get("payload")))

    # Recency signal: min-max normalized timestamps across the ranked pool.
    recency_scores: Dict[str, float] = {}
    recency_active = False
    if recency_weight > 0:
        timestamps: Dict[str, float] = {}
        for mem_id, _, payload in candidates:
            payload = payload or {}
            ts = _parse_timestamp(payload.get("updated_at"))
            if ts is None:
                ts = _parse_timestamp(payload.get("created_at"))
            if ts is not None:
                timestamps[mem_id] = ts
        if timestamps:
            recency_active = True
            min_ts = min(timestamps.values())
            span = max(timestamps.values()) - min_ts
            for mem_id, ts in timestamps.items():
                # No spread: every candidate is tied for newest.
                recency_scores[mem_id] = 1.0 if span <= 0 else (ts - min_ts) / span

    max_possible = 1.0
    if has_bm25:
        max_possible += 1.0
    if has_entity:
        max_possible += ENTITY_BOOST_WEIGHT
    if recency_active:
        max_possible += recency_weight

    scored: List[Dict[str, Any]] = []

    for mem_id, semantic_score, payload in candidates:
        bm25_score = bm25_scores.get(mem_id, 0.0)
        entity_boost = entity_boosts.get(mem_id, 0.0)
        recency_score = recency_scores.get(mem_id, 0.0)

        raw_combined = semantic_score + bm25_score + entity_boost + recency_weight * recency_score
        combined = min(raw_combined / max_possible, 1.0)

        scored_result = {
            "id": mem_id,
            "score": combined,
            "payload": payload,
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
            if recency_active:
                scored_result["score_details"]["recency_score"] = recency_score
                scored_result["score_details"]["recency_weight"] = recency_weight
        scored.append(scored_result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
