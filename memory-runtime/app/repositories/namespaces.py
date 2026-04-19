from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.namespace import Namespace


class NamespaceRepository:
    def __init__(self, session: Session):
        self.session = session

    def create(
        self,
        *,
        name: str,
        mode: str,
        source_systems: list[str],
    ) -> Namespace:
        namespace = Namespace(name=name, mode=mode, source_systems=source_systems)
        self.session.add(namespace)
        self.session.flush()
        return namespace

    def get_by_id(self, namespace_id: str) -> Namespace | None:
        return self.session.get(Namespace, namespace_id)

    def get_by_name(self, name: str) -> Namespace | None:
        stmt = select(Namespace).where(Namespace.name == name)
        return self.session.execute(stmt).scalar_one_or_none()
