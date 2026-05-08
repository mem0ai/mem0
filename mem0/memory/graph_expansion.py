"""Graph expansion over LLM-asserted memory links.

This module implements an optional retrieval-time step that expands a set of
semantically-retrieved "seed" memories with their 1-hop neighbours in the
implicit graph that the V3 extraction prompt already produces via the
``linked_memory_ids`` field.

The design is deliberately *not* dependent on any external graph database.
It only reads the ``linked_memory_ids`` list that is stored on each memory's
payload (persisted since the companion fix to the extraction pipeline) and
fetches the referenced memories through the existing vector-store API.

Theoretical motivation
----------------------
Mnemis (arXiv:2602.15313, Apr 2026 — current LoCoMo SOTA at 93.9) argues
that pure top-k semantic retrieval misses multi-hop cases where the bridging
evidence is semantically distant from the query. Mnemis's answer is a
"dual-route" design: System-1 fast vector retrieval + System-2 explicit
graph traversal over a separately built hierarchical graph.

We observe that mem0's V3 extraction prompt already instructs the LLM to
output memory-to-memory links (same-entity / updated-preference /
continuation / contradiction) at ADD time. Those links form a latent graph
whose edges are effectively free — they come out of the same single LLM
call that produces the facts. Reusing them at search time gives a
lightweight System-2 signal without adding a graph database dependency or
a second LLM call.

This module is framed narrowly around that idea: it has no opinion about
ranking, reranking, or score fusion beyond what is already in
``mem0.utils.scoring.score_and_rank``.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration knobs (kept as module-level constants for easy tuning).
# ---------------------------------------------------------------------------

# How many of the top scored candidates are treated as "seeds" whose links
# are followed. Keeping this small bounds the fan-out.
DEFAULT_SEED_K = 5

# Per-seed cap on the number of outgoing links to follow. Protects against
# hub memories that the LLM over-linked.
DEFAULT_MAX_LINKS_PER_SEED = 5

# Global cap on expanded memories added to the candidate pool in one search.
DEFAULT_MAX_EXPANDED = 20

# Score assigned to an expanded memory, as a fraction of the best seed's
# semantic score. Chosen to keep expanded items competitive but never
# ranked above a strong direct semantic hit.
DEFAULT_EXPANSION_SCORE_WEIGHT = 0.85


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def collect_expansion_ids(
    scored_results: List[Dict[str, Any]],
    *,
    seed_k: int = DEFAULT_SEED_K,
    max_links_per_seed: int = DEFAULT_MAX_LINKS_PER_SEED,
    max_expanded: int = DEFAULT_MAX_EXPANDED,
) -> Tuple[List[str], Dict[str, float]]:
    """Collect 1-hop neighbour ids from the top ``seed_k`` scored seeds.

    This function is intentionally pure — no I/O, no vector store access —
    so it can be unit-tested in isolation with lightweight dicts.

    Args:
        scored_results: Output of ``score_and_rank`` (or any equivalent
            list of dicts with ``id``, ``score``, ``payload`` keys). Must
            be sorted by ``score`` descending.
        seed_k: Number of top results to expand from.
        max_links_per_seed: Per-seed cap on outgoing links.
        max_expanded: Global cap on unique expanded ids returned.

    Returns:
        ``(expansion_ids, seed_scores)`` where

        - ``expansion_ids`` is the ordered list of unique neighbour ids to
          fetch. It never contains ids already present in ``scored_results``
          (i.e. already in the candidate pool).
        - ``seed_scores`` maps each expanded id to the best (highest) score
          of any seed that pointed to it. Used later to compute the
          expansion score.
    """
    if not scored_results or seed_k <= 0 or max_expanded <= 0:
        return [], {}

    seed_ids = {str(r["id"]) for r in scored_results if "id" in r}

    seen: Dict[str, float] = {}
    ordered: List[str] = []

    for seed in scored_results[:seed_k]:
        seed_score = float(seed.get("score", 0.0) or 0.0)
        payload = seed.get("payload") or {}
        links = payload.get("linked_memory_ids") or []
        if not isinstance(links, list):
            continue

        count_for_this_seed = 0
        for link in links:
            if not isinstance(link, str) or not link:
                continue
            if link in seed_ids:
                continue  # already a direct candidate
            # Update best-seed-score for this neighbour.
            prev = seen.get(link)
            if prev is None:
                ordered.append(link)
                seen[link] = seed_score
                count_for_this_seed += 1
            elif seed_score > prev:
                seen[link] = seed_score
            # Note: we keep counting only unique neighbours toward the
            # per-seed cap to prevent a single duplicated link from
            # starving others; the check runs after the insert above.
            if count_for_this_seed >= max_links_per_seed:
                break

            if len(ordered) >= max_expanded:
                return ordered, seen

    return ordered, seen


def build_expanded_candidates(
    fetched: Iterable[Any],
    seed_scores: Dict[str, float],
    *,
    expansion_score_weight: float = DEFAULT_EXPANSION_SCORE_WEIGHT,
) -> List[Dict[str, Any]]:
    """Turn fetched memory objects into scored candidate dicts.

    Args:
        fetched: Iterable of objects returned from the vector store; each
            must expose at least ``id`` and ``payload`` (a dict with
            ``data`` etc.). Objects missing a payload or ``data`` are
            dropped so they don't poison downstream ranking.
        seed_scores: Mapping produced by :func:`collect_expansion_ids`.
        expansion_score_weight: Multiplier applied to the best seed score
            to derive the expanded memory's score.

    Returns:
        List of candidate dicts suitable for append-then-resort alongside
        the original scored results. The score is bounded to ``[0, 1]``.
    """
    out: List[Dict[str, Any]] = []
    for mem in fetched:
        if mem is None:
            continue
        mem_id = getattr(mem, "id", None)
        if mem_id is None and isinstance(mem, dict):
            mem_id = mem.get("id")
        if mem_id is None:
            continue
        mem_id = str(mem_id)

        payload = getattr(mem, "payload", None)
        if payload is None and isinstance(mem, dict):
            payload = mem.get("payload")
        if not isinstance(payload, dict) or not payload.get("data"):
            continue

        seed_score = seed_scores.get(mem_id, 0.0)
        raw = seed_score * expansion_score_weight
        score = max(0.0, min(raw, 1.0))

        out.append({
            "id": mem_id,
            "score": score,
            "payload": payload,
            # Marker for downstream inspection / telemetry. Safe to ignore.
            "_source": "graph_expansion",
        })
    return out


# ---------------------------------------------------------------------------
# Orchestrator — combines pure helpers with a store-agnostic fetcher.
# ---------------------------------------------------------------------------


def expand_with_links(
    scored_results: List[Dict[str, Any]],
    fetcher: Callable[[List[str]], Iterable[Any]],
    *,
    seed_k: int = DEFAULT_SEED_K,
    max_links_per_seed: int = DEFAULT_MAX_LINKS_PER_SEED,
    max_expanded: int = DEFAULT_MAX_EXPANDED,
    expansion_score_weight: float = DEFAULT_EXPANSION_SCORE_WEIGHT,
) -> List[Dict[str, Any]]:
    """Run one 1-hop expansion step and return merged, re-sorted candidates.

    Merging rule: if an expanded id happens to already be in the input
    ``scored_results`` (shouldn't happen, but guard anyway), the original
    candidate is kept. Otherwise expanded candidates are appended and the
    full list is resorted by ``score`` descending.

    Args:
        scored_results: Input candidates (already scored and ranked).
        fetcher: Callable that takes a list of memory ids and returns an
            iterable of memory objects. The :class:`Memory` class supplies
            an adapter around ``vector_store.get(...)`` with graceful
            per-id failure handling.

    Returns:
        A new list. ``scored_results`` is not mutated.
    """
    expansion_ids, seed_scores = collect_expansion_ids(
        scored_results,
        seed_k=seed_k,
        max_links_per_seed=max_links_per_seed,
        max_expanded=max_expanded,
    )
    if not expansion_ids:
        return list(scored_results)

    try:
        fetched = list(fetcher(expansion_ids))
    except Exception as exc:
        # Graph expansion is an optional booster — never fail the query.
        logger.warning(f"Graph expansion fetch failed: {exc}")
        return list(scored_results)

    expanded = build_expanded_candidates(
        fetched, seed_scores, expansion_score_weight=expansion_score_weight
    )
    if not expanded:
        return list(scored_results)

    existing_ids = {str(r.get("id")) for r in scored_results}
    merged: List[Dict[str, Any]] = list(scored_results)
    for cand in expanded:
        if cand["id"] in existing_ids:
            continue
        merged.append(cand)

    merged.sort(key=lambda x: x.get("score", 0.0), reverse=True)
    return merged


# ---------------------------------------------------------------------------
# Store-agnostic fetcher adapter.
# ---------------------------------------------------------------------------


def make_vector_store_fetcher(vector_store) -> Callable[[List[str]], List[Any]]:
    """Build a fetcher that works with any :class:`VectorStoreBase`.

    Prefers ``get_batch`` if the store implements it (e.g. some providers
    may add it in the future); falls back to per-id ``get`` with individual
    error handling.
    """

    def _fetch(ids: List[str]) -> List[Any]:
        if not ids:
            return []

        # Optional fast path for stores that implement batch get.
        batch = getattr(vector_store, "get_batch", None)
        if callable(batch):
            try:
                result = batch(ids)
                if result is not None:
                    return list(result)
            except Exception as exc:
                logger.debug(f"get_batch failed, falling back to per-id get: {exc}")

        out: List[Any] = []
        for mid in ids:
            try:
                mem = vector_store.get(vector_id=mid)
                if mem is not None:
                    out.append(mem)
            except Exception as exc:
                logger.debug(f"Graph expansion skip (get {mid} failed): {exc}")
        return out

    return _fetch


__all__ = [
    "DEFAULT_EXPANSION_SCORE_WEIGHT",
    "DEFAULT_MAX_EXPANDED",
    "DEFAULT_MAX_LINKS_PER_SEED",
    "DEFAULT_SEED_K",
    "build_expanded_candidates",
    "collect_expansion_ids",
    "expand_with_links",
    "make_vector_store_fetcher",
]
