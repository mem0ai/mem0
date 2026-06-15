"""Internal project catalog helpers.

Implements the idempotent upsert of the project catalog described in the
TechSpec ("Modelos de Dados -> ProjectCatalog") and ADR-002: spaces represent
the company's projects and are auto-created/auto-cataloged by the memory itself,
without manual administration.

The catalog is materialized on the first write of each project. The background
worker (task_06) calls :func:`upsert_project` when it processes a write so that
a new project is registered the first time it is seen and subsequent writes are
a no-op (no duplicate row, no error).

Persistence is SQLite-backed through the existing SQLAlchemy stack
(``app.database``); a custom ``session`` can be injected for testing against a
temporary database.
"""

from typing import Optional

from app.database import SessionLocal
from app.models import Project
from sqlalchemy.orm import Session


def upsert_project(
    name: str,
    hostname: Optional[str] = None,
    session: Optional[Session] = None,
) -> Project:
    """Idempotently register ``name`` in the project catalog.

    On the first sighting of ``name`` a new :class:`~app.models.Project` row is
    created with ``first_seen_hostname`` set to ``hostname`` and ``created_at``
    populated automatically. If the project already exists this is a no-op: the
    existing row is returned unchanged and no error is raised.

    Args:
        name: Unique project identifier (primary key of ``projects``).
        hostname: Host that first triggered the project's creation. Recorded
            only on creation (``first_seen_hostname``); ignored if the project
            already exists.
        session: Optional SQLAlchemy session to reuse (e.g. the worker's
            session or a test session). When omitted, a short-lived session is
            opened via ``SessionLocal`` and committed/closed internally.

    Returns:
        The existing or newly-created :class:`~app.models.Project` row.
    """
    if session is not None:
        return _upsert(session, name, hostname)

    db = SessionLocal()
    try:
        return _upsert(db, name, hostname)
    finally:
        db.close()


def _upsert(db: Session, name: str, hostname: Optional[str]) -> Project:
    project = db.query(Project).filter(Project.name == name).first()
    if project is not None:
        # Already cataloged -- idempotent no-op.
        return project

    project = Project(name=name, first_seen_hostname=hostname)
    db.add(project)
    db.commit()
    db.refresh(project)
    return project
