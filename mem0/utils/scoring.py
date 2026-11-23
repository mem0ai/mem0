"""
Scoring utilities for hybrid retrieval.

Provides:
- **BM25 normalization**: Sigmoid normalization of raw BM25 scores to [0, 1].
- **BM25 parameter selection**: Query-length-adaptive sigmoid parameters.
- **Combined scoring**: semantic + BM25 + entity boost, normalized to [0, 1].
- **Recency discount**: optional multiplicative freshness discount on the
  combined score, anchored at query time (issue #7535).
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


def _parse_timestamp(value: Any) -> Optional[datetime]:
    """Best-effort parse of a memory timestamp into an aware UTC datetime.

    Accepts datetime objects (naive assumed UTC), ISO-8601 strings, and
    numeric epoch seconds. Returns None for anything unparseable so callers
    can treat the memory as having no recency signal.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, bool):
        return None
    elif isinstance(value, (int, float)):
        try:
            dt = datetime.fromtimestamp(value, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    elif isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text[-1] in ("Z", "z"):
            text = text[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(text)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _recency_score(payload: Any, now: datetime, tau_days: float) -> float:
    """Harmonic decay of a candidate's age: 1 / (1 + age_days / tau_days).

    Anchored at the query time `now` rather than normalized within the
    candidate set, so a candidate's recency is independent of which other
    candidates were retrieved (issue #7535; min-max normalization in PR #7538
    was candidate-set dependent and could flip a pair's relative order when
    an unrelated candidate entered the survivor set).

    Effective time per memory: updated_at, falling back to created_at.
    Missing or unparseable timestamps score 0. Future timestamps (age < 0)
    clamp to recency 1.0.
    """
    if not isinstance(payload, dict):
        return 0.0
    ts = _parse_timestamp(payload.get("updated_at") or payload.get("created_at"))
    if ts is None:
        return 0.0
    age_days = max((now - ts).total_seconds() / 86400.0, 0.0)
    if tau_days <= 0:
        # Degenerate half-life: the limit of the harmonic kernel.
        return 1.0 if age_days == 0.0 else 0.0
    return 1.0 / (1.0 + age_days / tau_days)


def score_and_rank(
    semantic_results: List[Dict[str, Any]],
    bm25_scores: Dict[str, float],
    entity_boosts: Dict[str, float],
    threshold: float,
    top_k: int,
    explain: bool = False,
    recency_weight: float = 0.0,
    recency_tau_days: float = 365.0,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """Score candidates and return top-k results.

    For each candidate:
        base = (semantic + bm25 + entity_boost) / max_possible
        combined = base * (1 - recency_weight * (1 - recency))   # when recency is active
                 = base                                          # otherwise

    Threshold gates the semantic score BEFORE combining -- candidates
    below the threshold are excluded even if BM25/entity would boost them.

    The divisor adapts based on which relevance signals are active:
        - Semantic only: max_possible = 1.0
        - Semantic + BM25: max_possible = 2.0
        - Semantic + BM25 + entity: max_possible = 2.5
        - Semantic + entity (no BM25): max_possible = 1.5

    Recency is a multiplicative discount on the relevance base, not an
    additive term: a memory always keeps at least 1 - recency_weight of its
    base score, so freshness can never erase relevance evidence outright.
    Because the discount scales with the base, being fresh gains little
    absolute ground for a weak match (relevance gates the recency effect),
    and the ordering is scale-free -- multiplying every base by the same
    factor (e.g. unbounded engine scores such as Elasticsearch _score)
    leaves the ranking unchanged.

    Args:
        semantic_results: Candidate memories from vector search.
        bm25_scores: Normalized keyword scores keyed by memory ID.
        entity_boosts: Entity-link boosts keyed by memory ID.
        threshold: Minimum semantic score required before hybrid scoring.
        top_k: Maximum number of results to return.
        explain: Include score_details in each result when true.
        recency_weight: Maximum fraction of its own base score that an
            infinitely old memory loses to the freshness discount
            (score floor = base * (1 - recency_weight)). 0.0 (default)
            disables the discount; negative values disable it. The
            suggested activation value is 0.25.
        recency_tau_days: Decay scale in days; recency is 0.5 when a memory's
            age equals recency_tau_days.
        now: Reference time for age computation; defaults to the current UTC
            time (naive values are assumed UTC). Injectable for deterministic
            scoring.

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
    has_bm25 = bool(bm25_scores)
    has_entity = bool(entity_boosts)
    recency_active = recency_weight > 0

    max_possible = 1.0
    if has_bm25:
        max_possible += 1.0
    if has_entity:
        max_possible += ENTITY_BOOST_WEIGHT

    if recency_active:
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

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
        recency_score = _recency_score(result.get("payload"), now, recency_tau_days) if recency_active else 0.0

        raw_combined = semantic_score + bm25_score + entity_boost
        base = min(raw_combined / max_possible, 1.0)
        discount = 1.0 - recency_weight * (1.0 - recency_score) if recency_active else 1.0
        combined = base * discount

        scored_result = {
            "id": mem_id_str,
            "score": combined,
            "payload": result.get("payload"),
        }
        if explain:
            score_details = {
                "semantic_score": semantic_score,
                "bm25_score": bm25_score,
                "entity_boost": entity_boost,
                "raw_score": raw_combined,
                "max_possible_score": max_possible,
                "final_score": combined,
                "threshold": threshold,
            }
            if recency_active:
                score_details["recency_score"] = recency_score
                score_details["recency_weight"] = recency_weight
                score_details["discount"] = discount
            scored_result["score_details"] = score_details
        scored.append(scored_result)

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]
