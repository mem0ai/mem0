"""
Cluster-aware retrieval for mem0 search results.

Read-time clustering groups topically related memories that the vector
store returned for a query (for example, three statements about the
user's current employer asserted at different times) so that the consumer
of `search()` can see the whole cluster, with timestamps, instead of just
the single best semantic match.

The module is intentionally narrow:

* It does **not** mutate or supersede any stored memory. The
  append-only philosophy of the v3 pipeline is preserved.
* It does **not** introduce any new vector store schema. Clustering is
  performed in-memory on whatever the existing `_search_vector_store`
  call already returns.
* It has a single public function, `cluster_memories`, that the sync
  and async search paths call when the user opts in via
  `expand_clusters=True`.

See issue mem0ai/mem0#4956.
"""

from __future__ import annotations

import logging
import math
from typing import Any, Callable, List, Optional, Sequence

logger = logging.getLogger(__name__)

# Sentinel keys we attach to each result.
CLUSTER_ID_KEY = "cluster_id"
CLUSTER_SIZE_KEY = "cluster_size"
CLUSTER_ROLE_KEY = "cluster_role"
CLUSTER_ROLE_PRIMARY = "primary"
CLUSTER_ROLE_SIBLING = "sibling"

# Defaults exposed to callers.
DEFAULT_CLUSTER_THRESHOLD = 0.85
DEFAULT_CLUSTER_TOP_K_MULTIPLIER = 3
DEFAULT_CLUSTER_MAX_SIZE = 5


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Compute cosine similarity between two equal-length numeric vectors.

    Returns 0.0 if either vector is empty or has zero magnitude.
    """
    if not a or not b:
        return 0.0
    if len(a) != len(b):
        # Mismatched dimensions almost certainly indicates a mixed-provider
        # bug upstream; do not silently coerce.
        raise ValueError(f"cosine_similarity: vectors have different dimensions ({len(a)} vs {len(b)})")

    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _validate_cluster_params(
    *,
    threshold: float,
    top_k_multiplier: int,
    max_cluster_size: int,
) -> None:
    if not (0.0 <= threshold <= 1.0):
        raise ValueError(f"cluster_threshold must be in [0.0, 1.0]; got {threshold!r}")
    if top_k_multiplier < 1:
        raise ValueError(f"cluster_top_k_multiplier must be >= 1; got {top_k_multiplier!r}")
    if max_cluster_size < 1:
        raise ValueError(f"cluster_max_size must be >= 1; got {max_cluster_size!r}")


def cluster_memories(
    memories: List[dict],
    *,
    embed_batch: Callable[[List[str]], List[Sequence[float]]],
    top_k: int,
    threshold: float = DEFAULT_CLUSTER_THRESHOLD,
    max_cluster_size: int = DEFAULT_CLUSTER_MAX_SIZE,
    text_key: str = "memory",
) -> List[dict]:
    """Group `memories` into clusters by pairwise embedding similarity.

    Inputs are assumed to be already sorted by relevance to the query
    (highest score first). Output keeps the original ordering but tags
    each item with cluster metadata and truncates to the top
    `top_k` *clusters* (not items), including all siblings of those
    clusters up to `max_cluster_size`.

    The clustering algorithm is greedy single-link with **anchor**
    comparison: each new item is compared only to the first member of
    each existing cluster, which is the highest-scoring memory in that
    cluster because we iterate in score-descending order. This avoids
    the classic transitive-chaining failure of pure single-link.

    Args:
        memories: List of result dicts (sorted by score desc) returned
            from `_search_vector_store`.
        embed_batch: A callable that takes a list of strings and returns
            a list of embedding vectors in the same order. Passing it
            in lets sync and async callers share this function.
        top_k: Maximum number of clusters to return.
        threshold: Minimum cosine similarity to anchor for an item to
            join a cluster. Higher values cluster only near-duplicates;
            lower values group more loosely.
        max_cluster_size: Cap on number of members per cluster. Excess
            members are dropped (they remain stored, just not surfaced
            for this query).
        text_key: Key in each memory dict that contains the text to
            embed.

    Returns:
        A new list of dicts, each carrying additional keys:
            - `cluster_id`: stable identifier within this response
              (e.g., "c0", "c1").
            - `cluster_size`: total members in the cluster.
            - `cluster_role`: "primary" for the highest-scoring member,
              "sibling" for the rest.

        Singleton clusters still get the metadata, with role "primary"
        and size 1.
    """
    _validate_cluster_params(
        threshold=threshold,
        top_k_multiplier=1,  # already-fetched here; only validate the others
        max_cluster_size=max_cluster_size,
    )
    if top_k < 1:
        raise ValueError(f"top_k must be >= 1; got {top_k!r}")

    if not memories:
        return []

    # If everything we received is a singleton possibility, skip the
    # embedding round trip entirely.
    if len(memories) == 1:
        only = dict(memories[0])
        only[CLUSTER_ID_KEY] = "c0"
        only[CLUSTER_SIZE_KEY] = 1
        only[CLUSTER_ROLE_KEY] = CLUSTER_ROLE_PRIMARY
        return [only]

    texts = [str(m.get(text_key, "")) for m in memories]
    try:
        candidate_embeddings = embed_batch(texts)
    except Exception as e:  # noqa: BLE001 — broad on purpose; clustering is opt-in
        logger.warning(
            "cluster_memories: embedding failed (%s); returning unclustered results",
            e,
        )
        return list(memories)[:top_k]

    if len(candidate_embeddings) != len(memories):
        logger.warning(
            "cluster_memories: embed_batch returned %d vectors for %d memories; returning unclustered results",
            len(candidate_embeddings),
            len(memories),
        )
        return list(memories)[:top_k]

    # Greedy anchor-based clustering. Iterate in input order (which is
    # score-descending), so the first-added member of each cluster is its
    # anchor and the highest-scoring member of that cluster.
    clusters: List[List[int]] = []
    for i, emb in enumerate(candidate_embeddings):
        joined = False
        for cluster in clusters:
            anchor_emb = candidate_embeddings[cluster[0]]
            if cosine_similarity(emb, anchor_emb) >= threshold:
                if len(cluster) < max_cluster_size:
                    cluster.append(i)
                # Always mark as joined so we don't open a duplicate
                # cluster — items past max_cluster_size are simply dropped
                # from this response's view of that cluster.
                joined = True
                break
        if not joined:
            clusters.append([i])

    # Keep only the top_k clusters by primary score (already in order).
    clusters = clusters[:top_k]

    enriched: List[dict] = []
    for cluster_idx, member_indices in enumerate(clusters):
        cluster_id = f"c{cluster_idx}"
        size = len(member_indices)
        for position, mem_idx in enumerate(member_indices):
            item = dict(memories[mem_idx])  # shallow copy; safe to mutate
            item[CLUSTER_ID_KEY] = cluster_id
            item[CLUSTER_SIZE_KEY] = size
            item[CLUSTER_ROLE_KEY] = CLUSTER_ROLE_PRIMARY if position == 0 else CLUSTER_ROLE_SIBLING
            enriched.append(item)

    return enriched


def resolve_cluster_kwargs(
    *,
    expand_clusters: bool,
    cluster_threshold: Optional[float],
    cluster_top_k_multiplier: Optional[int],
    cluster_max_size: Optional[int],
) -> dict[str, Any]:
    """Normalize the cluster knobs passed via Memory.search(**kwargs).

    Returns a dict with concrete values for `threshold`,
    `top_k_multiplier`, and `max_cluster_size`. Raises `ValueError`
    early on out-of-range values so callers get a useful traceback.
    """
    threshold = DEFAULT_CLUSTER_THRESHOLD if cluster_threshold is None else float(cluster_threshold)
    top_k_multiplier = (
        DEFAULT_CLUSTER_TOP_K_MULTIPLIER if cluster_top_k_multiplier is None else int(cluster_top_k_multiplier)
    )
    max_cluster_size = DEFAULT_CLUSTER_MAX_SIZE if cluster_max_size is None else int(cluster_max_size)

    if expand_clusters:
        _validate_cluster_params(
            threshold=threshold,
            top_k_multiplier=top_k_multiplier,
            max_cluster_size=max_cluster_size,
        )

    return {
        "threshold": threshold,
        "top_k_multiplier": top_k_multiplier,
        "max_cluster_size": max_cluster_size,
    }
