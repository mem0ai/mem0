"""Sync the active Mem0 API key into other ecosystem touchpoints.

Why this exists:
  The CLI canonical state lives in ``~/.mem0/config.json``. But MCP servers
  (Claude Code plugin, Codex plugin, etc.) read ``MEM0_API_KEY`` from env
  vars or their own config files. Without a sync, an agent-mode bootstrap
  mints a new key into config.json but the plugin's MCP keeps using the
  old key from env — silent surprise.

Design:
  - Update ONLY entries that already exist (never create new ones)
  - Preserve all surrounding content / formatting / other keys
  - Atomic writes (tmpfile + rename) so a crash mid-write doesn't corrupt
  - Idempotent — re-running with the same key is a no-op
  - Skip on dry_run

Targets currently handled:
  - ``~/.claude/settings.json::env::MEM0_API_KEY`` (Claude Code env injection)
  - ``~/.zshrc`` / ``~/.bashrc`` ``export MEM0_API_KEY="..."`` lines

Out of scope (deliberately not touched):
  - Codex / Cursor MCP configs — would require schema-aware edits and
    those tools don't have mem0 entries by default
  - Plugin's own ``<plugin-dir>/.api_key`` file — plugin-managed
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import tempfile
from pathlib import Path

# Files we know how to update safely.
_CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"
_SHELL_RCS = [Path.home() / ".zshrc", Path.home() / ".bashrc", Path.home() / ".bash_profile"]


def sync_api_key(api_key: str) -> list[str]:
    """Propagate ``api_key`` into known ecosystem touchpoints.

    Returns the list of paths actually updated. Empty list means nothing
    needed updating (either targets didn't exist or already had this value).
    """
    if not api_key:
        return []
    updated: list[str] = []
    if _update_claude_settings(_CLAUDE_SETTINGS, api_key):
        updated.append(str(_CLAUDE_SETTINGS))
    for rc in _SHELL_RCS:
        if _update_shell_rc(rc, api_key):
            updated.append(str(rc))
    return updated


def _update_claude_settings(path: Path, api_key: str) -> bool:
    """Update ``env.MEM0_API_KEY`` in path. Returns True if file was changed."""
    if not path.is_file():
        return False
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    env = data.get("env")
    if not isinstance(env, dict) or "MEM0_API_KEY" not in env:
        # No existing entry — don't create one.
        return False
    if env["MEM0_API_KEY"] == api_key:
        return False  # already in sync
    env["MEM0_API_KEY"] = api_key
    _atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return True


# Match `export MEM0_API_KEY="..."` (or single quotes, or no quotes).
# Use [ \t]* (not \s*) for trailing whitespace so a trailing newline at
# end-of-file is preserved when MEM0_API_KEY is the last line.
_RC_LINE = re.compile(
    r'^([ \t]*export[ \t]+MEM0_API_KEY[ \t]*=[ \t]*)(["\']?)([^"\'\n]*)(["\']?)[ \t]*$',
    re.MULTILINE,
)


def _update_shell_rc(path: Path, api_key: str) -> bool:
    """Update an existing ``export MEM0_API_KEY=...`` line in path."""
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return False
    match = _RC_LINE.search(text)
    if not match:
        return False  # no existing line
    if match.group(3) == api_key:
        return False
    new_text = _RC_LINE.sub(lambda m: f'{m.group(1)}"{api_key}"', text, count=1)
    _atomic_write_text(path, new_text)
    return True


def _atomic_write_text(path: Path, content: str) -> None:
    """Write content to path atomically (temp + rename)."""
    dirname = path.parent
    fd, tmp_path = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=dirname)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        # Preserve mode if the original existed.
        if path.exists():
            os.chmod(tmp_path, path.stat().st_mode & 0o777)
        os.replace(tmp_path, path)
    except Exception:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise
