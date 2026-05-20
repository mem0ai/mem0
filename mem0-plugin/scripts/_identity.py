"""Resolve mem0 user_id.

Resolution priority:
  1. MEM0_USER_ID env var (explicit override)
  2. $USER, else "default"
"""

from __future__ import annotations

import os


def resolve_user_id() -> str:
    explicit = os.environ.get("MEM0_USER_ID", "").strip()
    if explicit:
        return explicit
    return os.environ.get("USER") or "default"


try:
    from _project import resolve_branch, resolve_project_id, save_project_mapping
except ImportError:
    def resolve_project_id() -> str:
        return os.path.basename(os.getcwd())

    def resolve_branch() -> str:
        return "unknown"

    def save_project_mapping(cwd: str, project_id: str) -> None:
        pass
