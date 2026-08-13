"""Resolve the project's mem0 extraction policy from ``mem0.md``.

A repo's ``mem0.md`` can carry two prose sections that steer what Mem0 extracts:

    ## Instructions
    Remember architecture decisions and conventions. Ignore debug noise and secrets.

    ## Agent Instructions
    For agent-scoped memories, focus on the tools and task outcomes.

``## Instructions`` maps to Mem0's ``custom_instructions`` (user/project-scoped
extraction) and ``## Agent Instructions`` to ``agent_custom_instructions``
(agent-scoped extraction). Both are passed verbatim on memory writes, so the
policy lives in the repo, travels with it, and is shared by the whole team.

The hook writers call :func:`load_instructions` and merge the result into their
``/v3/memories/add`` body. Returns only the keys that are actually set, so a
project with no policy adds nothing.
"""

from __future__ import annotations

import os

from parse_mem0_config import load_full_config


def load_instructions(cwd: str | None = None) -> dict[str, str]:
    """Return the extraction policy for the project at *cwd* (defaults to the
    ``MEM0_CWD`` env var, then the process cwd).

    Keys (present only when non-empty):
      - ``custom_instructions``       from ``## Instructions``
      - ``agent_custom_instructions`` from ``## Agent Instructions``
    """
    if cwd is None:
        cwd = os.environ.get("MEM0_CWD") or os.getcwd()

    try:
        config = load_full_config(cwd)
    except Exception:
        return {}

    out: dict[str, str] = {}
    custom = config.get("instructions")
    if isinstance(custom, str) and custom.strip():
        out["custom_instructions"] = custom.strip()
    agent = config.get("agent_instructions")
    if isinstance(agent, str) and agent.strip():
        out["agent_custom_instructions"] = agent.strip()
    return out
