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
    candidate_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Score candidates with additive or reciprocal rank fusion and return top-k results.

    For each candidate:
        semantic_score is taken from the result's score field.
        combined = (semantic + bm25 + entity_boost) / max_possible

    In additive scoring, threshold gates the semantic score before combining.
    In RRF scoring, it gates only the semantic vote; auxiliary-only and
    below-threshold semantic candidates may qualify through positive keyword
    or entity support when a payload record is supplied.

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
        fusion_strategy: "additive" (default) or "rrf".
        rrf_k: Positive integer rank offset for RRF. Not the number of results.
        candidate_results: Optional payload-bearing records from auxiliary
            routes. Only RRF uses these records to admit IDs outside the
            semantic route.

    Returns:
        List of scored result dicts sorted by combined score descending.
    """
    if fusion_strategy not in ("additive", "rrf"):
        raise ValueError("fusion_strategy must be 'additive' or 'rrf'")
    if isinstance(rrf_k, bool) or not isinstance(rrf_k, int) or rrf_k <= 0:
        raise ValueError("rrf_k must be a positive integer")
    if fusion_strategy == "rrf":
        return _rrf_score_and_rank(
            semantic_results,
            bm25_scores,
            entity_boosts,
            threshold,
            top_k,
            explain,
            rrf_k,
            candidate_results,
        )

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
    candidate_results: Optional[List[Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """Fuse the complete semantic, keyword, and entity route windows.

    The route maps intentionally remain independent from the final payload
    candidate map.  This preserves the source position of a candidate even
    when another route supplied an ID that cannot be returned (for example,
    because its payload was missing).  ``candidate_results`` is the only way
    for an auxiliary-only ID to acquire a returnable payload.
    """

    def _finite(value: Any) -> Optional[float]:
        if isinstance(value, bool) or value is None:
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    def _record_value(record: Any, key: str, default: Any = None) -> Any:
        if isinstance(record, dict):
            return record.get(key, default)
        return getattr(record, key, default)

    def _payload_has_data(payload: Any) -> bool:
        return isinstance(payload, dict) and isinstance(payload.get("data"), str) and bool(payload.get("data"))

    def _merge_payload(memory_id: str, payload: Any) -> None:
        """Keep the first dict payload, upgrading an empty one with data."""
        if not isinstance(payload, dict):
            return
        existing = payloads.get(memory_id)
        if existing is None or (not _payload_has_data(existing) and _payload_has_data(payload)):
            payloads[memory_id] = payload

    # Vector stores normally return unique IDs.  For duplicate semantic IDs,
    # keep the first-seen route order but use the maximum finite score so a
    # later stronger hit cannot be discarded.
    semantic_scores: Dict[str, float] = {}
    payloads: Dict[str, Any] = {}
    semantic_order: List[str] = []
    seen_semantic_ids = set()
    for result in semantic_results:
        memory_id = _record_value(result, "id")
        if memory_id is None:
            continue
        memory_id = str(memory_id)
        if memory_id not in seen_semantic_ids:
            seen_semantic_ids.add(memory_id)
            semantic_order.append(memory_id)
        semantic_score = _finite(_record_value(result, "score", 0.0))
        if semantic_score is not None:
            if memory_id not in semantic_scores or semantic_score > semantic_scores[memory_id]:
                semantic_scores[memory_id] = semantic_score
            _merge_payload(memory_id, _record_value(result, "payload"))

    # BM25 and entity maps are already route/window score maps.  Only positive
    # finite values vote in RRF; additive callers continue to pass normalized
    # values through the unchanged path above.
    keyword_scores: Dict[str, float] = {}
    keyword_order: List[str] = []
    for raw_id, raw_score in (bm25_scores or {}).items():
        memory_id = str(raw_id)
        score = _finite(raw_score)
        if score is None or score <= 0 or memory_id in keyword_scores:
            continue
        keyword_scores[memory_id] = score
        keyword_order.append(memory_id)

    entity_scores: Dict[str, float] = {}
    entity_order: List[str] = []
    positive_entities = []
    seen_entity_ids = set()
    for raw_id, raw_score in (entity_boosts or {}).items():
        memory_id = str(raw_id)
        score = _finite(raw_score)
        if score is None or score <= 0 or memory_id in seen_entity_ids:
            continue
        seen_entity_ids.add(memory_id)
        positive_entities.append((memory_id, score))
    positive_entities.sort(key=lambda item: (-item[1], item[0]))
    for memory_id, score in positive_entities:
        entity_scores[memory_id] = score
        entity_order.append(memory_id)

    # Existing semantic/keyword payloads take precedence over hydration
    # records, except that an empty payload may be upgraded by a valid one.
    # Non-dict payloads are never admitted to the final candidate map.
    for result in candidate_results or []:
        memory_id = _record_value(result, "id")
        if memory_id is None:
            continue
        memory_id = str(memory_id)
        _merge_payload(memory_id, _record_value(result, "payload"))

    rank_maps = [
        _average_ranks(semantic_scores),
        _average_ranks(keyword_scores),
        _average_ranks(entity_scores),
    ]
    active_channels = sum(bool(ranks) for ranks in rank_maps)

    # Build a deterministic union in route order.  Entity ordering is made
    # deterministic by the caller when equal boosts are present; preserving
    # insertion order here also keeps the scorer's legacy stable-tie behavior.
    route_order: List[str] = []
    seen_ids = set()
    for memory_id in [*semantic_order, *keyword_order, *entity_order]:
        if memory_id not in seen_ids:
            seen_ids.add(memory_id)
            route_order.append(memory_id)

    scored: List[Dict[str, Any]] = []
    for memory_id in route_order:
        if memory_id not in payloads:
            continue

        semantic_score = semantic_scores.get(memory_id)
        has_semantic_vote = semantic_score is not None and semantic_score >= threshold
        has_keyword_vote = memory_id in keyword_scores
        has_entity_vote = memory_id in entity_scores
        if not (has_semantic_vote or has_keyword_vote or has_entity_vote):
            continue

        ranks = [rank_map.get(memory_id) for rank_map in rank_maps]
        contributions = [0.0, 0.0, 0.0]
        if has_semantic_vote and ranks[0] is not None:
            contributions[0] = 1.0 / (rrf_k + ranks[0])
        if ranks[1] is not None:
            contributions[1] = 1.0 / (rrf_k + ranks[1])
        if ranks[2] is not None:
            contributions[2] = 1.0 / (rrf_k + ranks[2])

        score = contributions[0] + contributions[1] + contributions[2]
        entry = {"id": memory_id, "score": score, "payload": payloads[memory_id]}
        if explain:
            entry["score_details"] = {
                "semantic_score": semantic_score,
                "bm25_score": keyword_scores.get(memory_id, 0.0),
                "entity_boost": entity_scores.get(memory_id, 0.0),
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
