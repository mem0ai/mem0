"""Detect which AI agent is invoking the CLI via environment variables.

Used by `mem0 init` to:
  1. Decide whether to auto-bootstrap an Agent Mode key (positive agent signal).
  2. Tag the `agent_caller` PostHog property on the cli.init event.

Returns a canonical short name or None when no agent is detected. The list
is curated, not exhaustive — agents we don't recognise fall through to None,
which groups into the "unknown" bucket on dashboards.
"""

from __future__ import annotations

import os

_AGENT_CALLER_ENV: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("claude-code", ("CLAUDECODE", "CLAUDE_CODE")),
    ("cursor", ("CURSOR_AGENT", "CURSOR_SESSION_ID")),
    ("codex", ("CODEX_CLI", "OPENAI_CODEX")),
    ("cline", ("CLINE_AGENT", "CLINE")),
    ("continue", ("CONTINUE_AGENT", "CONTINUE_SESSION")),
    ("aider", ("AIDER_SESSION",)),
    ("goose", ("GOOSE_AGENT",)),
    ("windsurf", ("WINDSURF_AGENT",)),
)


def detect_agent_caller() -> str | None:
    """Return a canonical agent name if any agent env var is set, else None."""
    for name, env_vars in _AGENT_CALLER_ENV:
        if any(os.environ.get(v) for v in env_vars):
            return name
    return None
