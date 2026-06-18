"""Quality evaluation for governance (task_12)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable, Dict, List, Optional

from app.utils.metrics import RETRIEVAL_DUPLICATE_IN_TOPK_RATIO, RETRIEVAL_QUALITY_INDEX

logger = logging.getLogger(__name__)

_LAST_QUALITY: Dict[str, Any] = {
    "proxy_ratio": 0.0,
    "llm_index": None,
    "updated_at": None,
}


@dataclass
class QualitySnapshot:
    proxy_ratio: float
    llm_index: Optional[float]
    updated_at: str
    sample_size: int = 0
    details: Dict[str, Any] = field(default_factory=dict)


def compute_duplicate_proxy(results: List[dict], *, threshold: float = 0.85) -> float:
    """Estimate near-duplicate ratio in a search result list."""
    if len(results) < 2:
        RETRIEVAL_DUPLICATE_IN_TOPK_RATIO.set(0.0)
        return 0.0

    texts = [str(r.get("memory") or r.get("data") or "") for r in results]
    dup_pairs = 0
    comparisons = 0
    for i, left in enumerate(texts):
        for right in texts[i + 1 :]:
            comparisons += 1
            if not left or not right:
                continue
            shorter, longer = (left, right) if len(left) <= len(right) else (right, left)
            if shorter and shorter in longer:
                dup_pairs += 1
    ratio = dup_pairs / comparisons if comparisons else 0.0
    RETRIEVAL_DUPLICATE_IN_TOPK_RATIO.set(ratio)
    return ratio


def sample_search_results(
    *,
    project: str,
    memory_client_provider: Optional[Callable] = None,
    query: str = "recent project knowledge",
    top_k: int = 10,
) -> List[dict]:
    if memory_client_provider is None:
        from app.utils.memory import get_memory_client_safe

        memory_client_provider = get_memory_client_safe
    client = memory_client_provider()
    if client is None:
        return []
    from app.utils.partitioning import resolve_and_bind

    route = resolve_and_bind(client, project)
    embeddings = client.embedding_model.embed(query, "search")
    hits = client.vector_store.search(
        query=query,
        vectors=embeddings,
        top_k=top_k,
        filters={"project": project},
        shard_key_selector=route.shard_key,
    )
    return [
        {"memory": (h.payload or {}).get("data"), "score": h.score, "id": str(h.id)}
        for h in hits
    ]


def run_llm_judge(
    results: List[dict],
    *,
    llm_client,
) -> Optional[float]:
    if not results or llm_client is None:
        return None
    prompt = (
        "Rate retrieval quality from 0.0 to 1.0 for duplicate/contradiction/obsolescence. "
        'Respond JSON {"quality_index": float}.\n'
        f"Results: {json.dumps(results[:10])}"
    )
    try:
        response = llm_client.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response)
        index = float(data.get("quality_index", 0))
        RETRIEVAL_QUALITY_INDEX.set(index)
        return index
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM judge failed: %s", exc)
        return None


def run_quality_eval_job(
    *,
    project: Optional[str],
    memory_client_provider: Optional[Callable] = None,
    llm_provider: Optional[Callable] = None,
) -> QualitySnapshot:
    project = project or "__global__"
    results = []
    if project != "__global__":
        results = sample_search_results(
            project=project, memory_client_provider=memory_client_provider
        )
    proxy = compute_duplicate_proxy(results)

    llm_index = None
    if llm_provider:
        llm = llm_provider()
        llm_index = run_llm_judge(results, llm_client=llm)
    elif memory_client_provider is not None:
        client = memory_client_provider()
        llm_index = run_llm_judge(results, llm_client=getattr(client, "llm", None))

    snap = QualitySnapshot(
        proxy_ratio=proxy,
        llm_index=llm_index,
        updated_at=datetime.now(UTC).isoformat(),
        sample_size=len(results),
    )
    _LAST_QUALITY.update(
        {
            "proxy_ratio": snap.proxy_ratio,
            "llm_index": snap.llm_index,
            "updated_at": snap.updated_at,
            "sample_size": snap.sample_size,
        }
    )
    return snap


def get_last_quality() -> Dict[str, Any]:
    return dict(_LAST_QUALITY)
