"""Resolve mem0 identity: API key, user_id, and settings.

API key resolution (first non-empty wins):
  1. MEM0_API_KEY env var (explicit / shell profile)
  2. CLAUDE_PLUGIN_OPTION_API_KEY (set by `claude plugin configure mem0`)
  3. CLAUDE_PLUGIN_OPTION_MEM0_API_KEY (legacy userConfig)
  4. ~/.mem0/config.json platform.api_key (from mem0 CLI)

User ID resolution:
  1. MEM0_USER_ID env var (explicit override)
  2. $USER, else "default"

Settings resolution:
  ~/.mem0/settings.json (user-editable, falls back to defaults)
"""

from __future__ import annotations

import os


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
    try:
        from load_settings import load_api_key_from_cli_config
        return load_api_key_from_cli_config()
    except ImportError:
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
            "output_style": "compact",
            "debug": False,
            "skip_tools": ["Read", "Glob", "Grep"],
            "capture_tools": ["Edit", "Write", "Bash"],
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
