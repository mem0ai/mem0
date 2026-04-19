from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.config import get_settings
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.episodes import EpisodeRepository
from app.repositories.namespaces import NamespaceRepository
from app.schemas.recall import (
    MemoryBrief,
    RecallFeedbackRequest,
    RecallFeedbackResponse,
    RecallRequest,
    RecallResponse,
    RecallTrace,
)
from app.services.mem0_bridge import ExternalMemoryResult, build_mem0_bridge
from app.telemetry.metrics import increment_metric


TOKEN_RE = re.compile(r"[a-zA-Z0-9_]+")
STOPWORDS = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "for",
    "to",
    "of",
    "what",
    "already",
    "about",
    "any",
    "we",
    "keep",
}


@dataclass
class RetrievalCandidate:
    episode_id: str
    space_type: str
    event_type: str
    summary: str
    raw_text: str
    importance_hint: str
    created_at: datetime | str
    session_id: str | None
    usefulness_score: float = 0.0


class RetrievalService:
    def __init__(self, session: Session):
        self.session = session
        self.namespaces = NamespaceRepository(session)
        self.episodes = EpisodeRepository(session)
        self.audit = AuditLogRepository(session)
        self.mem0_bridge = build_mem0_bridge(get_settings())

    def recall(self, payload: RecallRequest) -> RecallResponse:
        namespace = self.namespaces.get_by_id(payload.namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{payload.namespace_id}' not found")

        space_filters = self.resolve_space_filters(
            namespace_mode=namespace.mode,
            requested_space_filter=payload.space_filter,
        )
        rows = self.episodes.list_for_recall(
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            space_types=space_filters,
        )
        feedback_scores = self.audit.feedback_score_by_entity(
            namespace_id=payload.namespace_id,
            entity_type="episode",
            entity_ids=[episode.id for episode, _space_type in rows],
        )

        candidates = [
            RetrievalCandidate(
                episode_id=episode.id,
                space_type=space_type,
                event_type=self._extract_event_type(episode.summary),
                summary=episode.summary,
                raw_text=episode.raw_text,
                importance_hint=episode.importance_hint,
                created_at=episode.created_at,
                session_id=episode.session_id,
                usefulness_score=feedback_scores.get(episode.id, 0.0),
            )
            for episode, space_type in rows
        ]
        external_candidates = self._external_candidates(
            query=payload.query,
            namespace_id=payload.namespace_id,
            agent_id=payload.agent_id,
        )
        candidates.extend(external_candidates)

        ranked = self.rank_candidates(payload.query, candidates, payload.session_id)
        brief_dict = self.build_memory_brief(ranked)
        selected_space_types = self.collect_selected_space_types(ranked)
        selected_episode_ids = self.collect_selected_episode_ids(ranked)

        selected_count = sum(len(items) for items in brief_dict.values())
        increment_metric("recall_requests_total")
        increment_metric("recall_candidates_total", len(candidates))
        increment_metric("recall_selected_total", selected_count)
        return RecallResponse(
            brief=MemoryBrief(**brief_dict),
            trace=RecallTrace(
                candidate_count=len(candidates),
                selected_count=selected_count,
                selected_space_types=selected_space_types,
                selected_episode_ids=selected_episode_ids,
            ),
        )

    def record_feedback(self, payload: RecallFeedbackRequest) -> RecallFeedbackResponse:
        namespace = self.namespaces.get_by_id(payload.namespace_id)
        if namespace is None:
            raise LookupError(f"Namespace '{payload.namespace_id}' not found")

        action = "recall_feedback_positive" if payload.helpful else "recall_feedback_negative"
        for episode_id in payload.episode_ids:
            self.audit.create(
                namespace_id=payload.namespace_id,
                agent_id=payload.agent_id,
                entity_type="episode",
                entity_id=episode_id,
                action=action,
                details_json={"query": payload.query, "notes": payload.notes},
            )
        self.session.commit()
        increment_metric(
            "recall_feedback_positive_total" if payload.helpful else "recall_feedback_negative_total",
            len(payload.episode_ids),
        )
        return RecallFeedbackResponse(recorded_count=len(payload.episode_ids), helpful=payload.helpful)

    @staticmethod
    def resolve_space_filters(namespace_mode: str, requested_space_filter: list[str] | None) -> list[str]:
        if requested_space_filter:
            return requested_space_filter

        defaults = ["session-space", "project-space", "agent-core"]
        if namespace_mode == "shared":
            defaults.append("shared-space")
        return defaults

    @classmethod
    def rank_candidates(
        cls,
        query: str,
        candidates: list[RetrievalCandidate],
        active_session_id: str | None = None,
    ) -> list[RetrievalCandidate]:
        def score(candidate: RetrievalCandidate) -> tuple[float, float]:
            overlap = cls._token_overlap(query, f"{candidate.summary} {candidate.raw_text}")
            importance = {"high": 2.0, "medium": 1.0, "normal": 0.0}.get(candidate.importance_hint, 0.0)
            session_boost = 1.0 if active_session_id and candidate.session_id == active_session_id else 0.0
            recency = cls._recency_score(candidate.created_at)
            usefulness = candidate.usefulness_score * 3.0
            total = overlap * 10.0 + importance + session_boost + recency + usefulness
            return total, recency

        return sorted(candidates, key=score, reverse=True)

    @classmethod
    def build_memory_brief(cls, ranked_candidates: list[RetrievalCandidate]) -> dict[str, list[str]]:
        brief = {
            "critical_facts": [],
            "active_project_context": [],
            "prior_decisions": [],
            "standing_procedures": [],
            "recent_session_carryover": [],
        }

        seen = {key: set() for key in brief}
        for candidate in ranked_candidates:
            item = f"{candidate.space_type}: {candidate.summary}"
            slot = cls._slot_for_candidate(candidate)
            if item not in seen[slot]:
                brief[slot].append(item)
                seen[slot].add(item)
        return brief

    @staticmethod
    def collect_selected_space_types(ranked_candidates: list[RetrievalCandidate]) -> list[str]:
        selected_space_types: list[str] = []
        for candidate in ranked_candidates:
            if candidate.space_type not in selected_space_types:
                selected_space_types.append(candidate.space_type)
        return selected_space_types

    @staticmethod
    def collect_selected_episode_ids(ranked_candidates: list[RetrievalCandidate]) -> list[str]:
        selected_episode_ids: list[str] = []
        for candidate in ranked_candidates:
            if candidate.episode_id.startswith("mem0:"):
                continue
            if candidate.episode_id not in selected_episode_ids:
                selected_episode_ids.append(candidate.episode_id)
        return selected_episode_ids

    @staticmethod
    def _extract_event_type(summary: str) -> str:
        if ":" not in summary:
            return "conversation_turn"
        return summary.split(":", 1)[0].strip().lower()

    @staticmethod
    def _slot_for_candidate(candidate: RetrievalCandidate) -> str:
        if candidate.space_type == "session-space":
            return "recent_session_carryover"
        if candidate.event_type in {"architecture_decision", "decision"}:
            return "prior_decisions"
        if candidate.space_type == "agent-core" or candidate.event_type in {"policy_update", "procedure", "rule"}:
            return "standing_procedures"
        if candidate.space_type in {"project-space", "shared-space"}:
            return "active_project_context"
        return "critical_facts"

    @staticmethod
    def _normalize_tokens(text: str) -> set[str]:
        return {
            token
            for token in (match.group(0).lower() for match in TOKEN_RE.finditer(text))
            if token not in STOPWORDS and len(token) > 1
        }

    @classmethod
    def _token_overlap(cls, query: str, text: str) -> float:
        query_tokens = cls._normalize_tokens(query)
        if not query_tokens:
            return 0.0
        text_tokens = cls._normalize_tokens(text)
        if not text_tokens:
            return 0.0
        return len(query_tokens & text_tokens) / len(query_tokens)

    @staticmethod
    def _recency_score(value: datetime | str) -> float:
        if isinstance(value, str):
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                return 0.0
        else:
            parsed = value
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        age_seconds = max((datetime.now(timezone.utc) - parsed).total_seconds(), 0)
        return 1.0 / (1.0 + age_seconds / 3600)

    def _external_candidates(
        self,
        *,
        query: str,
        namespace_id: str,
        agent_id: str | None,
    ) -> list[RetrievalCandidate]:
        try:
            increment_metric("mem0_search_requests_total")
            results = self.mem0_bridge.search(
                query=query,
                namespace_id=namespace_id,
                agent_id=agent_id,
                limit=5,
            )
        except Exception:  # noqa: BLE001
            return []
        return [self._candidate_from_external_result(result) for result in results]

    @staticmethod
    def _candidate_from_external_result(result: ExternalMemoryResult) -> RetrievalCandidate:
        content = result.content.strip()
        summary = f"external_memory: {content}"
        return RetrievalCandidate(
            episode_id=f"mem0:{result.external_id}",
            space_type=result.space_type,
            event_type="external_memory",
            summary=summary,
            raw_text=content,
            importance_hint="medium",
            created_at=datetime.now(timezone.utc),
            session_id=None,
            usefulness_score=0.0,
        )
