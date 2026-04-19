from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.episode import Episode
from app.repositories.audit_logs import AuditLogRepository
from app.repositories.memory_spaces import MemorySpaceRepository
from app.repositories.jobs import JobRepository
from app.repositories.memory_units import MemoryUnitRepository
from app.services.mem0_bridge import build_mem0_bridge
from app.telemetry.metrics import increment_metric


WS_RE = re.compile(r"\s+")
NON_WORD_RE = re.compile(r"[^a-z0-9\s]+")
TOKEN_RE = re.compile(r"[a-z0-9]+")
DECISION_PREFIXES = (
    "we decided to ",
    "we chose to ",
    "decision: ",
    "decided to ",
    "chose to ",
    "use ",
    "keep ",
)
PROCEDURE_PREFIXES = (
    "always ",
    "the agent should ",
    "agent should ",
    "you should ",
    "should ",
    "must ",
    "first ",
)
NEGATION_TOKENS = {"not", "never", "no", "deprecated", "avoid", "stop"}
FILLER_TOKENS = {
    "we",
    "do",
    "the",
    "a",
    "an",
    "to",
    "for",
    "of",
    "as",
    "and",
    "or",
    "that",
    "this",
    "is",
    "are",
    "be",
    "should",
    "must",
    "always",
    "agent",
}


class ConsolidationService:
    def __init__(self, session: Session):
        self.session = session
        self.memory_units = MemoryUnitRepository(session)
        self.spaces = MemorySpaceRepository(session)
        self.audit = AuditLogRepository(session)
        self.jobs = JobRepository(session)
        self.mem0_bridge = build_mem0_bridge()

    def consolidate_episode(self, episode: Episode, space_type: str) -> tuple[str, str]:
        event_type = self._extract_event_type(episode.summary)
        content = self.build_memory_content(episode.summary)
        kind, scope = self.infer_memory_attributes(
            space_type=space_type,
            event_type=event_type,
            content=content,
        )
        merge_key = self.normalize_merge_key(content)

        existing = None
        if episode.space_id:
            existing = self.memory_units.find_by_merge_key(
                namespace_id=episode.namespace_id,
                primary_space_id=episode.space_id,
                merge_key=merge_key,
            )

        contradictory = None
        if existing is None and episode.space_id:
            contradictory = self.find_contradictory_memory(
                namespace_id=episode.namespace_id,
                primary_space_id=episode.space_id,
                kind=kind,
                content=content,
            )

        if existing is None and contradictory is None:
            memory_unit = self.memory_units.create(
                namespace_id=episode.namespace_id,
                agent_id=episode.agent_id,
                primary_space_id=episode.space_id,
                kind=kind,
                scope=scope,
                content=content,
                summary=episode.summary,
                merge_key=merge_key,
                created_from_episode_id=episode.id,
                importance_score=self._importance_score(episode.importance_hint),
            )
            self.audit.create(
                namespace_id=episode.namespace_id,
                agent_id=episode.agent_id,
                entity_type="memory_unit",
                entity_id=memory_unit.id,
                action="memory_unit_created",
                details_json={"episode_id": episode.id, "space_type": space_type},
            )
            self.jobs.create(
                job_type="memory_decay",
                payload_json={"memory_unit_id": memory_unit.id, "space_type": space_type},
            )
            self._sync_to_mem0(memory_unit, episode, space_type)
            increment_metric("consolidation_created_total")
            self.session.flush()
            return "created", memory_unit.id

        if contradictory is not None:
            contradictory.status = "superseded"
            contradictory.updated_at = datetime.now(timezone.utc)
            memory_unit = self.memory_units.create(
                namespace_id=episode.namespace_id,
                agent_id=episode.agent_id,
                primary_space_id=episode.space_id,
                kind=kind,
                scope=scope,
                content=content,
                summary=episode.summary,
                merge_key=merge_key,
                created_from_episode_id=episode.id,
                supersedes_memory_id=contradictory.id,
                importance_score=self._importance_score(episode.importance_hint),
            )
            self.audit.create(
                namespace_id=episode.namespace_id,
                agent_id=episode.agent_id,
                entity_type="memory_unit",
                entity_id=memory_unit.id,
                action="memory_unit_superseded",
                details_json={
                    "episode_id": episode.id,
                    "space_type": space_type,
                    "supersedes_memory_id": contradictory.id,
                },
            )
            self.jobs.create(
                job_type="memory_decay",
                payload_json={"memory_unit_id": memory_unit.id, "space_type": space_type},
            )
            self._sync_to_mem0(memory_unit, episode, space_type)
            increment_metric("consolidation_created_total")
            self.session.flush()
            return "superseded", memory_unit.id

        existing.summary = episode.summary
        existing.content = content
        existing.kind = kind
        existing.scope = scope
        existing.importance_score = max(existing.importance_score, self._importance_score(episode.importance_hint))
        existing.freshness_score = 1.0
        existing.updated_at = datetime.now(timezone.utc)
        self.audit.create(
            namespace_id=episode.namespace_id,
            agent_id=episode.agent_id,
            entity_type="memory_unit",
            entity_id=existing.id,
            action="memory_unit_merged",
            details_json={"episode_id": episode.id, "space_type": space_type},
        )
        self.jobs.create(
            job_type="memory_decay",
            payload_json={"memory_unit_id": existing.id, "space_type": space_type},
        )
        self._sync_to_mem0(existing, episode, space_type)
        increment_metric("consolidation_merged_total")
        self.session.flush()
        return "merged", existing.id

    @staticmethod
    def infer_memory_attributes(*, space_type: str, event_type: str, content: str) -> tuple[str, str]:
        if event_type in {"architecture_decision", "decision"}:
            return "decision", "long-term"
        if space_type == "agent-core" or event_type in {"policy_update", "procedure", "rule"}:
            return "procedure", "long-term"
        if space_type in {"project-space", "shared-space"} and ConsolidationService.looks_like_decision(content):
            return "decision", "long-term"
        if space_type in {"project-space", "agent-core", "shared-space"} and ConsolidationService.looks_like_procedure(
            content
        ):
            return "procedure", "long-term"
        if space_type == "shared-space":
            return "shared_fact", "long-term"
        if space_type == "project-space":
            return "fact", "long-term"
        return "episodic_summary", "short-term"

    @staticmethod
    def build_memory_content(summary: str) -> str:
        if ":" not in summary:
            return summary.strip()
        return summary.split(":", 1)[1].strip()

    @staticmethod
    def normalize_merge_key(content: str) -> str:
        normalized = ConsolidationService._normalize_text(content)
        prefixes = DECISION_PREFIXES + PROCEDURE_PREFIXES
        while True:
            updated = normalized
            for prefix in prefixes:
                if updated.startswith(prefix):
                    updated = updated[len(prefix) :]
                    break
            if updated == normalized:
                break
            normalized = updated
        normalized = WS_RE.sub(" ", normalized).strip()
        return normalized

    @staticmethod
    def _extract_event_type(summary: str) -> str:
        if ":" not in summary:
            return "conversation_turn"
        return summary.split(":", 1)[0].strip().lower()

    @staticmethod
    def _importance_score(importance_hint: str) -> float:
        return {"high": 0.95, "medium": 0.7, "normal": 0.5}.get(importance_hint, 0.5)

    def find_contradictory_memory(
        self,
        *,
        namespace_id: str,
        primary_space_id: str,
        kind: str,
        content: str,
    ):
        topic_key = self.topic_key(content)
        if not topic_key:
            return None
        candidate_is_negative = self.is_negative_statement(content)
        active_memories = self.memory_units.list_active_in_space(
            namespace_id=namespace_id,
            primary_space_id=primary_space_id,
            kind=kind,
        )
        for memory in active_memories:
            if self.topic_key(memory.content) != topic_key:
                continue
            if self.is_negative_statement(memory.content) == candidate_is_negative:
                continue
            return memory
        return None

    @staticmethod
    def looks_like_decision(content: str) -> bool:
        normalized = ConsolidationService._normalize_text(content)
        return normalized.startswith(
            (
                "we decided to ",
                "we chose to ",
                "decision ",
                "decided to ",
                "chose to ",
                "we will use ",
                "we will keep ",
                "use ",
                "keep ",
            )
        )

    @staticmethod
    def looks_like_procedure(content: str) -> bool:
        normalized = ConsolidationService._normalize_text(content)
        if normalized.startswith(PROCEDURE_PREFIXES):
            return True
        return " first " in f" {normalized} " and " then " in f" {normalized} "

    @staticmethod
    def is_negative_statement(content: str) -> bool:
        tokens = set(ConsolidationService._tokens(content))
        return any(token in tokens for token in NEGATION_TOKENS)

    @staticmethod
    def topic_key(content: str) -> str:
        tokens = [
            token
            for token in ConsolidationService._tokens(content)
            if token not in NEGATION_TOKENS and token not in FILLER_TOKENS
        ]
        return " ".join(tokens[:6])

    @staticmethod
    def _normalize_text(content: str) -> str:
        normalized = content.strip().lower()
        normalized = NON_WORD_RE.sub(" ", normalized)
        return WS_RE.sub(" ", normalized).strip()

    @staticmethod
    def _tokens(content: str) -> list[str]:
        return [match.group(0) for match in TOKEN_RE.finditer(ConsolidationService._normalize_text(content))]

    def _sync_to_mem0(self, memory_unit, episode: Episode, space_type: str) -> None:
        increment_metric("mem0_sync_attempts_total")
        try:
            self.mem0_bridge.sync_memory(
                memory_unit=memory_unit,
                namespace_id=episode.namespace_id,
                agent_id=episode.agent_id,
                space_type=space_type,
            )
        except Exception:  # noqa: BLE001
            return
        increment_metric("mem0_sync_success_total")
