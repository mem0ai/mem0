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
