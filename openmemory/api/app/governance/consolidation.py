"""Semantic consolidation pipeline (task_10 / ADR-004)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from app.database import SessionLocal
from app.models import Memory, MemoryState
from app.utils.governance_policy import EffectivePolicy, resolve_policy
from app.utils.metrics import (
    GOVERNANCE_CONTRADICTIONS_RESOLVED_TOTAL,
    GOVERNANCE_MERGED_TOTAL,
)
from app.utils.quarantine import QuarantineEngine
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationCandidate:
    source_id: str
    target_id: str
    score: float
    project: str
    mem_type: str


def _is_pinned_payload(payload: dict) -> bool:
    return bool((payload or {}).get("pinned"))


def find_candidates(
    *,
    project: str,
    policy: EffectivePolicy,
    vector_store,
    embedding_model,
    limit: int = 50,
) -> List[ConsolidationCandidate]:
    filters = {"project": project, "state": "active"}
    scroll_result = vector_store.list(filters=filters, top_k=limit * 4)
    points = scroll_result[0] if isinstance(scroll_result, tuple) else (scroll_result or [])
    candidates: List[ConsolidationCandidate] = []
    seen: set[Tuple[str, str]] = set()

    active_points = []
    for p in points or []:
        payload = p.payload or {}
        if payload.get("state") == "quarantined" or _is_pinned_payload(payload):
            continue
        active_points.append(p)

    for i, base in enumerate(active_points):
        payload = base.payload or {}
        text = payload.get("data") or ""
        if not text:
            continue
        vec = embedding_model.embed(text, "search")
        results = vector_store.search(
            query=text,
            vectors=vec,
            top_k=5,
            filters={"project": project, "type": payload.get("type", "memory")},
        )
        for hit in results:
            if str(hit.id) == str(base.id):
                continue
            hp = hit.payload or {}
            if hp.get("state") == "quarantined" or _is_pinned_payload(hp):
                continue
            if hit.score is None or hit.score < policy.similarity_threshold:
                continue
            pair = tuple(sorted([str(base.id), str(hit.id)]))
            if pair in seen:
                continue
            seen.add(pair)
            candidates.append(
                ConsolidationCandidate(
                    source_id=str(base.id),
                    target_id=str(hit.id),
                    score=float(hit.score),
                    project=project,
                    mem_type=str(payload.get("type", "memory")),
                )
            )
            if len(candidates) >= limit:
                return candidates
    return candidates


def adjudicate_pair(
    left: Memory,
    right: Memory,
    *,
    llm_client,
    tiebreak: str,
) -> str:
    """Return merge | contradiction | none."""
    if llm_client is None:
        return "none"
    prompt = (
        "Compare two memory statements and respond with JSON "
        '{"action":"merge|contradiction|none","canonical_text":"..."}.\n'
        f"A: {left.content}\nB: {right.content}\n"
        f"Tiebreak preference: {tiebreak}"
    )
    try:
        response = llm_client.generate_response(
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(response)
        action = str(data.get("action", "none")).lower()
        if action not in {"merge", "contradiction", "none"}:
            return "none"
        return action
    except Exception as exc:  # noqa: BLE001
        logger.warning("LLM adjudication failed: %s", exc)
        return "none"


def _pick_winner(left: Memory, right: Memory, tiebreak: str) -> Memory:
    if tiebreak == "confidence":
        lc = float((left.metadata_ or {}).get("confidence", 0))
        rc = float((right.metadata_ or {}).get("confidence", 0))
        if lc != rc:
            return left if lc >= rc else right
    # recency default
    lc = left.updated_at or left.created_at
    rc = right.updated_at or right.created_at
    return left if (lc or left.id) >= (rc or right.id) else right


def apply_merge(
    canonical: Memory,
    sources: List[Memory],
    *,
    canonical_text: str,
    engine: QuarantineEngine,
    job_id: str,
) -> int:
    canonical.content = canonical_text
    merged = 0
    for src in sources:
        if src.id == canonical.id or engine.is_pinned(src):
            continue
        if engine.quarantine(src.id, reason="semantic_merge", job_id=job_id):
            merged += 1
            GOVERNANCE_MERGED_TOTAL.inc()
    return merged


def run_consolidate_job(
    *,
    project: Optional[str],
    job_id: str,
    limit: int = 50,
    session_factory=SessionLocal,
    quarantine_engine: Optional[QuarantineEngine] = None,
    llm_provider: Optional[Callable] = None,
    memory_client_provider: Optional[Callable] = None,
) -> int:
    if not project:
        return 0
    policy = resolve_policy(project, session_factory=session_factory)
    if not policy.consolidation_enabled:
        return 0

    if memory_client_provider is None:
        from app.utils.memory import get_memory_client_safe

        memory_client_provider = get_memory_client_safe

    client = memory_client_provider()
    if client is None:
        return 0

    engine = quarantine_engine or QuarantineEngine(session_factory=session_factory)
    llm = llm_provider() if llm_provider else getattr(client, "llm", None)

    candidates = find_candidates(
        project=project,
        policy=policy,
        vector_store=client.vector_store,
        embedding_model=client.embedding_model,
        limit=min(limit, policy.batch_limit),
    )

    db: Session = session_factory()
    actions = 0
    try:
        for cand in candidates:
            left = db.query(Memory).filter(Memory.id == cand.source_id).first()
            right = db.query(Memory).filter(Memory.id == cand.target_id).first()
            if not left or not right:
                continue
            if left.state != MemoryState.active or right.state != MemoryState.active:
                continue
            decision = adjudicate_pair(left, right, llm_client=llm, tiebreak=policy.contradiction_tiebreak)
            if decision == "none":
                continue
            if decision == "merge":
                apply_merge(left, [left, right], canonical_text=left.content, engine=engine, job_id=job_id)
                actions += 1
            elif decision == "contradiction":
                winner = _pick_winner(left, right, policy.contradiction_tiebreak)
                loser = right if winner.id == left.id else left
                if not engine.is_pinned(loser) and engine.quarantine(
                    loser.id, reason="contradiction", job_id=job_id
                ):
                    GOVERNANCE_CONTRADICTIONS_RESOLVED_TOTAL.inc()
                    actions += 1
        db.commit()
        return actions
    finally:
        db.close()
