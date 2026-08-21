"""Resolve mem0 identity: API key, user_id, and settings.

API key resolution (first non-empty wins):
  1. MEM0_API_KEY env var (explicit / shell profile)
  2. CLAUDE_PLUGIN_OPTION_API_KEY (injected by Claude Code userConfig)
  3. CLAUDE_PLUGIN_OPTION_MEM0_API_KEY (legacy userConfig)
  4. Extract from shell profile files (~/.zshrc, ~/.bashrc, etc.)
     Desktop app doesn't inherit shell env — this covers users who
     set MEM0_API_KEY in their profile but use the Desktop app.

User ID resolution:
  1. MEM0_USER_ID env var (explicit override)
  2. $USER, else "default"

Settings resolution:
  ~/.mem0/settings.json (user-editable, falls back to defaults)
"""

from __future__ import annotations

import os
import re
from pathlib import Path


def _extract_key_from_shell_profiles() -> str:
    """Extract MEM0_API_KEY from shell profile files.

    The Desktop app only reads PATH from shell profiles — env vars like
    MEM0_API_KEY are not inherited. This handles the common
    ``export MEM0_API_KEY=...`` pattern without sourcing the full profile.
    """
    profiles = [".zshrc", ".bashrc", ".zprofile", ".bash_profile", ".profile"]
    pattern = re.compile(r'^\s*(?:export\s+)?MEM0_API_KEY=(.+)$')

    for name in profiles:
        path = Path.home() / name
        if not path.is_file():
            continue
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                m = pattern.match(line)
                if not m:
                    continue
                value = m.group(1).strip()
                value = re.sub(r'#.*$', '', value).strip()
                value = value.strip("\"'")
                if value and not value.startswith("$"):
                    return value
        except OSError:
            continue
    return ""


def resolve_api_key() -> str:
    key = os.environ.get("MEM0_API_KEY", "").strip()
    if key:
        return key
    key = os.environ.get("CLAUDE_PLUGIN_OPTION_API_KEY", "").strip()
    if key:
        return key
    key = os.environ.get("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", "").strip()
    if key:
        return key
    key = _extract_key_from_shell_profiles()
    if key:
        return key
    return ""


def resolve_user_id() -> str:
    explicit = os.environ.get("MEM0_USER_ID", "").strip()
    if explicit:
        return explicit
    return os.environ.get("USER") or "default"


def resolve_config() -> dict:
    """Resolve settings from ~/.mem0/settings.json (primary) with env var overrides."""
    try:
        from load_settings import load_settings
        return load_settings()
    except ImportError:
        return {
            "auto_save": True,
            "auto_search": True,
            "search_limit": 10,
            "retention_session_days": 90,
            "confidence_threshold": 0.3,
            "debug": False,
        }


try:
    from _project import resolve_branch, resolve_project_id, save_project_mapping
except ImportError:
    def resolve_project_id(cwd: str | None = None) -> str:
        return os.path.basename(cwd or os.getcwd())

    def resolve_branch(cwd: str | None = None) -> str:
        return "unknown"

    def save_project_mapping(cwd: str, project_id: str) -> None:
        pass


def global_search_filter(user_id: str) -> dict:
    """Filter for global search — the one definition every caller must use.

    The platform rejects wildcard-only filters with "filters must include at least
    one positively-scoped entity ID", so ``{"OR": [{"user_id": "*"}]}`` 400s. Anchoring
    the OR with a real ``user_id`` keeps it valid while ``agent_id: "*"`` still widens
    the search past the current project.

    This lives in one place deliberately. The same literal was previously duplicated
    across _search.py, session_timeline.py, enforce_metadata_defaults.sh and
    on_session_start.sh, and the last of those was missed in the first pass at this
    fix — it kept 400ing silently and showed ``memories=?`` in the session banner.
    A single definition makes that class of miss structurally impossible.

    Bash callers reach this the same way they reach load_settings::

        PYTHONPATH="$SCRIPT_DIR" python3 -c \
          "from _identity import global_search_filter; import json; \
           print(json.dumps(global_search_filter('$USER_ID')))"

    Note the scope: ``agent_id: "*"`` is NOT constrained by ``user_id``, so global
    search can surface agent-scoped memories belonging to other user IDs on the same
    account. That is the documented intent ("all memories, all users, all projects"),
    not a leak across accounts.
    """
    return {"OR": [{"user_id": user_id}, {"agent_id": "*"}]}
