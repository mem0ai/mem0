"""Resolve mem0 identity: API key and user_id.

API key resolution (first non-empty wins):
  1. MEM0_API_KEY env var (explicit / shell profile)
  2. CLAUDE_PLUGIN_OPTION_MEM0_API_KEY (set by Claude Code userConfig)

User ID resolution:
  1. MEM0_USER_ID env var (explicit override)
  2. $USER, else "default"
"""

from __future__ import annotations

import os


def resolve_api_key() -> str:
    key = os.environ.get("MEM0_API_KEY", "").strip()
    if key:
        return key
    return os.environ.get("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", "").strip()


def resolve_user_id() -> str:
    explicit = os.environ.get("MEM0_USER_ID", "").strip()
    if explicit:
        return explicit
    return os.environ.get("USER") or "default"


try:
    from _project import resolve_branch, resolve_project_id, save_project_mapping
except ImportError:
    def resolve_project_id(cwd: str | None = None) -> str:
        return os.path.basename(cwd or os.getcwd())

    def resolve_branch(cwd: str | None = None) -> str:
        return "unknown"

    def save_project_mapping(cwd: str, project_id: str) -> None:
        pass
