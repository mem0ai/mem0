from __future__ import annotations

from typing import Any

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditLogRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        namespace_id: str,
        agent_id: str | None,
        entity_type: str,
        entity_id: str,
        action: str,
        details_json: dict[str, Any] | None = None,
    ) -> AuditLog:
        entry = AuditLog(
            namespace_id=namespace_id,
            agent_id=agent_id,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            details_json=details_json or {},
        )
        self.session.add(entry)
        self.session.flush()
        return entry

    def feedback_score_by_entity(
        self,
        *,
        namespace_id: str,
        entity_type: str,
        entity_ids: list[str],
    ) -> dict[str, float]:
        if not entity_ids:
            return {}

        stmt = (
            select(
                AuditLog.entity_id,
                func.sum(
                    case(
                        (AuditLog.action == "recall_feedback_positive", 1),
                        (AuditLog.action == "recall_feedback_negative", -1),
                        else_=0,
                    )
                ),
            )
            .where(AuditLog.namespace_id == namespace_id)
            .where(AuditLog.entity_type == entity_type)
            .where(AuditLog.entity_id.in_(entity_ids))
            .where(AuditLog.action.in_(("recall_feedback_positive", "recall_feedback_negative")))
            .group_by(AuditLog.entity_id)
        )
        return {
            entity_id: float(score or 0)
            for entity_id, score in self.session.execute(stmt).all()
        }
