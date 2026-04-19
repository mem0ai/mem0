from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.memory_unit import MemoryUnit
from app.repositories.audit_logs import AuditLogRepository
from app.telemetry.metrics import increment_metric


@dataclass
class LifecycleDecision:
    action: str
    new_status: str
    new_freshness_score: float


class LifecycleService:
    def __init__(self, session: Session):
        self.session = session
        self.audit = AuditLogRepository(session)

    def apply_transition(
        self,
        *,
        memory_unit: MemoryUnit,
        space_type: str,
        now: datetime | None = None,
    ) -> str:
        effective_now = now or datetime.now(timezone.utc)
        decision = self.evaluate_transition(memory_unit=memory_unit, space_type=space_type, now=effective_now)
        if decision.action == "none":
            return "none"

        memory_unit.freshness_score = decision.new_freshness_score
        memory_unit.status = decision.new_status
        memory_unit.updated_at = effective_now

        audit_action = {
            "decayed": "memory_unit_decayed",
            "archived": "memory_unit_archived",
            "evicted": "memory_unit_evicted",
        }[decision.action]
        metric_name = {
            "decayed": "lifecycle_decayed_total",
            "archived": "lifecycle_archived_total",
            "evicted": "lifecycle_evicted_total",
        }[decision.action]

        self.audit.create(
            namespace_id=memory_unit.namespace_id,
            agent_id=memory_unit.agent_id,
            entity_type="memory_unit",
            entity_id=memory_unit.id,
            action=audit_action,
            details_json={"space_type": space_type, "status": decision.new_status},
        )
        increment_metric(metric_name)
        self.session.flush()
        return decision.action

    @classmethod
    def evaluate_transition(
        cls,
        *,
        memory_unit,
        space_type: str,
        now: datetime,
    ) -> LifecycleDecision:
        created_at = cls._normalize_datetime(memory_unit.created_at)
        age_hours = max((now - created_at).total_seconds() / 3600, 0.0)
        current_freshness = float(memory_unit.freshness_score)

        if getattr(memory_unit, "status", "active") != "active":
            return LifecycleDecision("none", getattr(memory_unit, "status", "active"), current_freshness)

        if space_type == "session-space" and age_hours >= 48:
            return LifecycleDecision("archived", "archived", current_freshness)

        decayed_freshness = cls._decayed_freshness(space_type=space_type, age_hours=age_hours, current=current_freshness)
        importance = float(getattr(memory_unit, "importance_score", 0.0))
        access_count = int(getattr(memory_unit, "access_count", 0))

        if space_type in {"project-space", "shared-space"} and age_hours >= 24 * 30 and decayed_freshness <= 0.25 and importance <= 0.2 and access_count == 0:
            return LifecycleDecision("evicted", "evicted", decayed_freshness)

        if decayed_freshness < current_freshness:
            return LifecycleDecision("decayed", "active", decayed_freshness)

        return LifecycleDecision("none", "active", current_freshness)

    @staticmethod
    def _normalize_datetime(value: datetime | str) -> datetime:
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                parsed = datetime.now(timezone.utc)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _decayed_freshness(*, space_type: str, age_hours: float, current: float) -> float:
        half_life_hours = {
            "session-space": 24.0,
            "project-space": 24.0 * 7,
            "shared-space": 24.0 * 14,
            "agent-core": 24.0 * 30,
        }.get(space_type, 24.0 * 7)
        if space_type != "session-space" and current >= 1.0:
            return 0.95
        decay = 1.0 / (1.0 + (age_hours / half_life_hours))
        next_score = round(min(current, decay), 4)
        return next_score
