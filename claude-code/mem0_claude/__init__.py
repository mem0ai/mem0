"""mem0 integration library for Claude Code hooks.

Centralizes capture, recall, client management, and context stripping
for reuse across any Claude Code project.

Usage:
    from mem0_claude.types import ProjectConfig
    from mem0_claude.capture import handle_stop, handle_subagent_stop
    from mem0_claude.recall import recall, recall_session_start
    from mem0_claude.client import load_env, get_client
    from mem0_claude.strip import strip_recalled_context
"""

__version__ = "0.1.0"

from .capture import (
    capture,
    handle_pre_compact,
    handle_session_end,
    handle_stop,
    handle_subagent_stop,
)
from .client import get_client, load_env, reset_client
from .recall import (
    format_context,
    recall,
    recall_session_start,
    recall_subagent_start,
    search_dual_scope,
)
from .strip import strip_recalled_context
from .types import ProjectConfig

__all__ = [
    "ProjectConfig",
    "capture",
    "handle_stop",
    "handle_subagent_stop",
    "handle_pre_compact",
    "handle_session_end",
    "recall",
    "recall_session_start",
    "recall_subagent_start",
    "search_dual_scope",
    "format_context",
    "load_env",
    "get_client",
    "reset_client",
    "strip_recalled_context",
]
