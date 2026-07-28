"""Filter recipes, every one verified against the live v2 API.

Rules encoded here (each learned the hard way -- see docs/CONTRACT.md):

* Implicit null scoping does NOT work. `{"user_id": u}` alone also returns
  project-scoped records, so user-scope reads need an explicit NOT clause.
* `NOT` takes a LIST, not an object. The object form returns HTTP 400.
* Type is matched on `metadata.type` (available immediately) OR on `categories`
  (assigned by a background job ~4h later). Reads union both so fresh and old
  memories are equally retrievable.
* Metadata filters support only equality/contains/ne -- multi-value needs OR.
"""

from __future__ import annotations

from typing import Any

from .project_config import DURABLE_TYPES

Filter = dict[str, Any]


def _type_clauses(types: tuple[str, ...] | list[str]) -> list[Filter]:
    """Match a set of types by metadata (immediate) or categories (eventual)."""
    clauses: list[Filter] = [{"metadata": {"type": t}} for t in types]
    clauses.append({"categories": {"in": list(types)}})
    return clauses


def _null_app() -> Filter:
    """Records with no app_id, i.e. user-scoped ones."""
    return {"NOT": [{"app_id": "*"}]}


def context_pack(user_id: str, app_id: str, types: tuple[str, ...] = DURABLE_TYPES) -> Filter:
    """Everything the session-start pack needs, in ONE call (~310ms measured).

    Spans both scopes: project-scoped records for this repo, plus the user's
    global preferences which carry no app_id.
    """
    return {
        "AND": [
            {"user_id": user_id},
            {"OR": [{"app_id": app_id}, _null_app()]},
            {"OR": _type_clauses(types)},
        ]
    }


def user_prefs(user_id: str) -> Filter:
    """User-scope only. Without the NOT clause this also returns every project record."""
    return {"AND": [{"user_id": user_id}, _null_app()]}


def project_scope(user_id: str, app_id: str, types: tuple[str, ...] | None = None) -> Filter:
    f: list[Filter] = [{"user_id": user_id}, {"app_id": app_id}]
    if types:
        f.append({"OR": _type_clauses(types)})
    return {"AND": f}


def session_state(user_id: str, app_id: str, session_id: str | None = None) -> Filter:
    """The open-thread record. One per session, found by metadata."""
    f: list[Filter] = [
        {"user_id": user_id},
        {"app_id": app_id},
        {"metadata": {"type": "session_state"}},
    ]
    if session_id:
        f.append({"metadata": {"session_id": session_id}})
    return {"AND": f}


def error_assist(user_id: str, app_id: str) -> Filter:
    """Past gotchas and procedures -- the only semantic search on the hot path."""
    return {
        "AND": [
            {"user_id": user_id},
            {"app_id": app_id},
            {"OR": _type_clauses(("insight", "runbook"))},
        ]
    }


def by_session(user_id: str, app_id: str, session_id: str) -> Filter:
    return {
        "AND": [
            {"user_id": user_id},
            {"app_id": app_id},
            {"metadata": {"session_id": session_id}},
        ]
    }


def all_in_scope(user_id: str, app_id: str) -> Filter:
    """Maintenance / stats: everything for this user+project."""
    return {"AND": [{"user_id": user_id}, {"app_id": app_id}]}


def team_scope(app_id: str) -> Filter:
    """Planned for the team fast-follow; not wired into v1 of the client."""
    return {"AND": [{"app_id": app_id}, {"user_id": "*"}]}
