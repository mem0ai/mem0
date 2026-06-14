"""
Access-control resolution for OpenMemory, resolved once per request.

The original implementation checked permissions per memory: for every memory it
re-queried the ``App`` row and recomputed the app's accessible set, turning a
single search into O(N) identical SQL queries (an N+1). These helpers resolve the
app and its access set exactly once, then offer O(1) membership checks against the
small result list.

Semantics of the accessible set:
- ``None``  -> the app may access ALL of the user's memories (no ACL rules).
- ``set()`` -> the app may access NONE (explicit global deny, or app paused).
- ``{...}`` -> the app may access exactly those memory ids.
"""

import uuid
from typing import Callable, Dict, List, Optional, Set
from uuid import UUID

from app.models import AccessControl, Memory, MemoryState
from sqlalchemy.orm import Session


def get_accessible_memory_ids(db: Session, app_id: UUID) -> Optional[Set[UUID]]:
    """Resolve the set of memory ids an app may access from its ACL rules.

    Returns ``None`` when no rules exist (all accessible) — the common case.
    """
    app_access = db.query(AccessControl).filter(
        AccessControl.subject_type == "app",
        AccessControl.subject_id == app_id,
        AccessControl.object_type == "memory",
    ).all()

    if not app_access:
        return None

    allowed_memory_ids: Set[UUID] = set()
    denied_memory_ids: Set[UUID] = set()

    for rule in app_access:
        if rule.effect == "allow":
            if rule.object_id:
                allowed_memory_ids.add(rule.object_id)
            else:
                return None  # allow-all rule
        elif rule.effect == "deny":
            if rule.object_id:
                denied_memory_ids.add(rule.object_id)
            else:
                return set()  # deny-all rule

    if allowed_memory_ids:
        allowed_memory_ids -= denied_memory_ids

    return allowed_memory_ids


def resolve_accessible_ids(db: Session, app) -> Optional[Set[UUID]]:
    """Resolve an app's accessible set once, accounting for the app being paused.

    ``app`` is an already-loaded ``App`` instance. Returns ``set()`` (none) if the
    app is inactive, otherwise delegates to :func:`get_accessible_memory_ids`.
    """
    if app is None or not app.is_active:
        return set()
    return get_accessible_memory_ids(db, app.id)


def filter_results_by_acl(
    results: List[Dict],
    accessible_ids: Optional[Set[UUID]],
) -> List[Dict]:
    """Filter vector-search result dicts (with string ``id``) by the access set."""
    if accessible_ids is None:
        return results
    allowed = {str(mid) for mid in accessible_ids}
    return [r for r in results if r.get("id") in allowed]


def filter_results_by_active_state(
    db: Session,
    user_pk: UUID,
    results: List[Dict],
) -> List[Dict]:
    """Drop results whose Postgres memory state is not ``active``.

    Vector search returns hits straight from Qdrant, which has no knowledge of the
    Postgres ``state``. Paused/archived memories keep their vectors (only delete
    removes them), so without this filter they would leak into search results.

    This MUST be applied live on every call (including cache hits), because the
    search cache stores pre-state results — a memory paused after the entry was
    cached must still be excluded. The query is scoped to the small candidate id
    list and uses the (user_id, state) index, so it is one cheap lookup.
    """
    if not results:
        return results

    candidate_ids = []
    for r in results:
        rid = r.get("id")
        if not rid:
            continue
        try:
            candidate_ids.append(uuid.UUID(rid))
        except (ValueError, TypeError, AttributeError):
            continue
    if not candidate_ids:
        return []

    rows = db.query(Memory.id).filter(
        Memory.user_id == user_pk,
        Memory.state == MemoryState.active,
        Memory.id.in_(candidate_ids),
    ).all()
    active = {str(row[0]) for row in rows}
    return [r for r in results if r.get("id") in active]


def make_memory_access_checker(
    db: Session,
    app_id: Optional[UUID],
    app=None,
) -> Callable[[Memory], bool]:
    """Build an O(1) per-memory access predicate, resolving app + ACL once.

    Replaces per-memory ``check_memory_access_permissions`` calls inside result
    loops. The returned predicate enforces: memory is active, app is active, and
    the memory is within the app's accessible set.

    Pass an already-loaded ``app`` instance to avoid re-querying it.
    """
    if app_id is None:
        # No app scoping requested: only the memory's own state matters.
        return lambda memory: memory.state == MemoryState.active

    if app is None:
        from app.models import App

        app = db.query(App).filter(App.id == app_id).first()
    if app is None or not app.is_active:
        return lambda memory: False

    accessible_ids = get_accessible_memory_ids(db, app_id)

    def _check(memory: Memory) -> bool:
        if memory.state != MemoryState.active:
            return False
        if accessible_ids is None:
            return True
        return memory.id in accessible_ids

    return _check
