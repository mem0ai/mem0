"""Detect whether the CLI is being invoked from inside an AI-agent context.

Used by `mem0 init` to auto-enter Agent Mode (Rule 3 bootstrap) when an
agent runtime env var is present. The return value is a context **trigger
only** — the canonical agent identity is self-declared by the agent via
``--agent-caller <name>`` (Proof Editor-style) and never sniffed from env
vars to fill the ``agent_caller`` field on the APIKey row.

Returns a short name or None. The list is curated, not exhaustive — env
vars we don't recognise fall through to None (caller treated as
non-agent). Honest reporting depends on ``--agent-caller``; this list is
just enough to enable the zero-friction auto-bootstrap UX.
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
