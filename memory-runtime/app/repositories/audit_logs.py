from __future__ import annotations

from typing import Any

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
