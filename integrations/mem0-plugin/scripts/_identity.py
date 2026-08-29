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

Base URL resolution (first non-empty wins):
  1. MEM0_BASE_URL env var (explicit override, for self-hosted servers)
  2. "base_url" in ~/.mem0/settings.json
  3. DEFAULT_BASE_URL (the hosted Mem0 Platform)
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


DEFAULT_BASE_URL = "https://api.mem0.ai"


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
            "base_url": "",
        }


def resolve_base_url() -> str:
    """Resolve the Mem0 API base URL: MEM0_BASE_URL env var, then settings.json, then the hosted platform."""
    explicit = os.environ.get("MEM0_BASE_URL", "").strip()
    if explicit:
        return explicit.rstrip("/")
    configured = str(resolve_config().get("base_url", "")).strip()
    if configured:
        return configured.rstrip("/")
    return DEFAULT_BASE_URL


try:
    from _project import resolve_branch, resolve_project_id, save_project_mapping
except ImportError:
    def resolve_project_id(cwd: str | None = None) -> str:
        return os.path.basename(cwd or os.getcwd())

    def resolve_branch(cwd: str | None = None) -> str:
        return "unknown"

    def save_project_mapping(cwd: str, project_id: str) -> None:
        pass
