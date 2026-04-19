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


class ConsolidationService:
    def __init__(self, session: Session):
        self.session = session
        self.memory_units = MemoryUnitRepository(session)
        self.spaces = MemorySpaceRepository(session)
        self.audit = AuditLogRepository(session)
        self.jobs = JobRepository(session)
        self.mem0_bridge = build_mem0_bridge()

    def consolidate_episode(self, episode: Episode, space_type: str) -> tuple[str, str]:
        kind, scope = self.infer_memory_attributes(space_type=space_type, event_type=self._extract_event_type(episode.summary))
        content = self.build_memory_content(episode.summary)
        merge_key = self.normalize_merge_key(content)

        existing = None
        if episode.space_id:
            existing = self.memory_units.find_by_merge_key(
                namespace_id=episode.namespace_id,
                primary_space_id=episode.space_id,
                merge_key=merge_key,
            )

        if existing is None:
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

        existing.summary = episode.summary
        existing.content = content
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
    def infer_memory_attributes(*, space_type: str, event_type: str) -> tuple[str, str]:
        if event_type in {"architecture_decision", "decision"}:
            return "decision", "long-term"
        if space_type == "agent-core" or event_type in {"policy_update", "procedure", "rule"}:
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
        normalized = WS_RE.sub(" ", content.strip().lower())
        return normalized

    @staticmethod
    def _extract_event_type(summary: str) -> str:
        if ":" not in summary:
            return "conversation_turn"
        return summary.split(":", 1)[0].strip().lower()

    @staticmethod
    def _importance_score(importance_hint: str) -> float:
        return {"high": 0.95, "medium": 0.7, "normal": 0.5}.get(importance_hint, 0.5)

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
