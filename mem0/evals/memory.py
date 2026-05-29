from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal


MemoryAction = Literal["add", "update", "query"]


@dataclass(frozen=True)
class MemoryEvent:
    """One state transition in a memory quality scenario."""

    action: MemoryAction
    text: str
    memory_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MemoryScenario:
    """Scenario for evaluating whether memory retrieval behaves correctly over time."""

    name: str
    user_id: str
    events: list[MemoryEvent]
    expected: str
    stale: list[str] = field(default_factory=list)
    top_k: int = 5
    match_threshold: float = 0.72


@dataclass(frozen=True)
class RetrievedMemory:
    """Normalized retrieved memory used by deterministic eval scoring."""

    text: str
    memory_id: str | None = None
    score: float | None = None
    rank: int | None = None
    raw: Any = None


@dataclass(frozen=True)
class MemoryEvalResult:
    """Deterministic retrieval-quality metrics for one memory scenario."""

    scenario_name: str
    query: str
    retrieved: list[RetrievedMemory]
    expected_best_match: RetrievedMemory | None
    expected_match_score: float
    stale_matches: list[RetrievedMemory]
    memory_recall_rate: float
    staleness_score: float
    conflict_resolution_acc: float
    update_propagation_rate: float


def evaluate_memory(client: Any, scenario: MemoryScenario) -> MemoryEvalResult:
    """Run a memory scenario against a Mem0-like client and score the final query.

    The evaluator is intentionally API-free: it works with the OSS `Memory` class,
    hosted `MemoryClient`, or a test double that exposes `add`, `update`, and `search`.
    """

    query = ""
    retrieved: list[RetrievedMemory] = []
    remembered_ids: dict[str, str] = {}

    for event in scenario.events:
        if event.action == "add":
            response = client.add(
                [{"role": "user", "content": event.text}],
                user_id=scenario.user_id,
                metadata=event.metadata or None,
            )
            if event.memory_id:
                created_id = _extract_first_memory_id(response)
                if created_id:
                    remembered_ids[event.memory_id] = created_id
        elif event.action == "update":
            memory_id = remembered_ids.get(event.memory_id or "", event.memory_id)
            if memory_id is None:
                raise ValueError("update events require memory_id")
            client.update(memory_id, event.text)
        elif event.action == "query":
            query = event.text
            response = client.search(
                query,
                top_k=scenario.top_k,
                filters={"user_id": scenario.user_id},
            )
            retrieved = normalize_search_results(response)
        else:
            raise ValueError(f"Unsupported memory action: {event.action}")

    if not query:
        raise ValueError("scenario must include a query event")

    return score_retrieval(
        scenario_name=scenario.name,
        query=query,
        retrieved=retrieved,
        expected=scenario.expected,
        stale=scenario.stale,
        match_threshold=scenario.match_threshold,
    )


def score_retrieval(
    *,
    scenario_name: str,
    query: str,
    retrieved: list[RetrievedMemory],
    expected: str,
    stale: list[str] | None = None,
    match_threshold: float = 0.72,
) -> MemoryEvalResult:
    """Score retrieved memories for recall, staleness, conflict ordering, and update propagation."""

    stale = stale or []
    expected_scores = [_token_f1(memory.text, expected) for memory in retrieved]
    best_index, best_score = _best_match(expected_scores)
    expected_best = retrieved[best_index] if best_index is not None and best_score >= match_threshold else None

    stale_matches = []
    for memory in retrieved:
        if any(_is_stale_match(memory.text, stale_text, match_threshold) for stale_text in stale):
            stale_matches.append(memory)

    memory_recall_rate = 1.0 if expected_best is not None else 0.0
    staleness_score = len(stale_matches) / len(retrieved) if retrieved else 0.0
    conflict_resolution_acc = _conflict_resolution_acc(expected_best, stale_matches)
    update_propagation_rate = 1.0 if expected_best is not None and not stale_matches else 0.0

    return MemoryEvalResult(
        scenario_name=scenario_name,
        query=query,
        retrieved=retrieved,
        expected_best_match=expected_best,
        expected_match_score=best_score,
        stale_matches=stale_matches,
        memory_recall_rate=memory_recall_rate,
        staleness_score=staleness_score,
        conflict_resolution_acc=conflict_resolution_acc,
        update_propagation_rate=update_propagation_rate,
    )


def normalize_search_results(response: Any) -> list[RetrievedMemory]:
    """Normalize OSS and hosted Mem0 search responses into ranked `RetrievedMemory` rows."""

    if isinstance(response, dict):
        results = response.get("results", response.get("memories", []))
    else:
        results = response

    normalized = []
    for rank, item in enumerate(results or [], start=1):
        text = _memory_text(item)
        if not text:
            continue
        normalized.append(
            RetrievedMemory(
                text=text,
                memory_id=_memory_id(item),
                score=_memory_score(item),
                rank=rank,
                raw=item,
            )
        )
    return normalized


def _conflict_resolution_acc(
    expected_best: RetrievedMemory | None,
    stale_matches: list[RetrievedMemory],
) -> float:
    if expected_best is None:
        return 0.0
    stale_ranks = [memory.rank for memory in stale_matches if memory.rank is not None]
    if not stale_ranks:
        return 1.0
    if expected_best.rank is None:
        return 0.0
    return 1.0 if expected_best.rank < min(stale_ranks) else 0.0


def _extract_first_memory_id(response: Any) -> str | None:
    if isinstance(response, dict):
        results = response.get("results") or []
        if results:
            return _memory_id(results[0])
        return _memory_id(response)
    if isinstance(response, list) and response:
        return _memory_id(response[0])
    return None


def _memory_text(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        payload = item.get("payload")
        if isinstance(payload, dict):
            return str(payload.get("data") or payload.get("memory") or payload.get("text") or "")
        return str(item.get("memory") or item.get("text") or item.get("data") or "")
    return str(getattr(item, "memory", None) or getattr(item, "text", None) or getattr(item, "data", "") or "")


def _memory_id(item: Any) -> str | None:
    if isinstance(item, dict):
        value = item.get("id") or item.get("memory_id")
        return str(value) if value is not None else None
    value = getattr(item, "id", None) or getattr(item, "memory_id", None)
    return str(value) if value is not None else None


def _memory_score(item: Any) -> float | None:
    if isinstance(item, dict):
        value = item.get("score")
    else:
        value = getattr(item, "score", None)
    return float(value) if value is not None else None


def _best_match(scores: list[float]) -> tuple[int | None, float]:
    if not scores:
        return None, 0.0
    best_score = max(scores)
    return scores.index(best_score), best_score


def _is_stale_match(candidate: str, stale_text: str, match_threshold: float) -> bool:
    return _token_f1(candidate, stale_text) >= max(match_threshold, 0.9)


def _token_f1(candidate: str, expected: str) -> float:
    candidate_tokens = _tokens(candidate)
    expected_tokens = _tokens(expected)
    if not candidate_tokens or not expected_tokens:
        return 0.0

    overlap = len(candidate_tokens & expected_tokens)
    if overlap == 0:
        return 0.0

    precision = overlap / len(candidate_tokens)
    recall = overlap / len(expected_tokens)
    return 2 * precision * recall / (precision + recall)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))
