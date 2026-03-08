"""Capture engine for Claude Code hooks.

Provides a unified capture function used by Stop, SubagentStop,
PreCompact, and SessionEnd hooks. Handles context stripping,
truncation, graph memory, session scoping, and expiration.
"""

import os
from datetime import datetime, timedelta
from typing import Optional

from .client import get_client
from .strip import strip_recalled_context
from .types import ProjectConfig


def _extract_session_id(hook_input: dict) -> Optional[str]:
    """Extract session ID from hook input or transcript path."""
    sid = hook_input.get("session_id")
    if sid:
        return sid
    tp = hook_input.get("transcript_path", "")
    if tp:
        return os.path.basename(os.path.dirname(tp))
    return None


def capture(
    hook_input: dict,
    config: ProjectConfig,
    *,
    source: str,
    agent_id: Optional[str] = None,
    min_chars: int = 50,
    max_chars: Optional[int] = None,
    expiry_days: Optional[int] = None,
    user_content: str = "[Session context for memory extraction]",
    includes: Optional[str] = None,
    excludes: Optional[str] = None,
) -> Optional[dict]:
    """Core capture logic shared by all capture hooks.

    Args:
        hook_input: Raw JSON from Claude Code hook stdin.
        config: Project-specific configuration.
        source: Metadata source tag (e.g., "claude-code-stop").
        agent_id: Override agent ID (defaults to config.agent_id_main).
        min_chars: Minimum message length to process.
        max_chars: Maximum message length before truncation.
        expiry_days: Auto-expiration in days (None = permanent).
        user_content: Synthetic user message for the extraction pair.
        includes: Per-request includes directive.
        excludes: Per-request excludes directive.

    Returns:
        The mem0 add() result dict, or None on skip/failure.
    """
    if max_chars is None:
        max_chars = config.max_capture_chars

    last_msg = hook_input.get("last_assistant_message", "")
    if not last_msg or len(last_msg.strip()) < min_chars:
        return None

    # Strip recalled memory blocks to prevent feedback loops
    cleaned = strip_recalled_context(last_msg)
    if not cleaned or len(cleaned.strip()) < min_chars:
        return None

    # Truncate very long messages
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars] + "\n... [truncated]"

    # Build message pair for extraction
    messages = [
        {"role": "user", "content": user_content},
        {"role": "assistant", "content": cleaned},
    ]

    session_id = _extract_session_id(hook_input)

    client = get_client()
    if not client:
        return None

    add_kwargs = dict(
        user_id=config.user_id,
        agent_id=agent_id or config.agent_id_main,
        app_id=config.app_id,
        enable_graph=True,
        version="v2",
        output_format="v1.1",
        metadata={
            "source": source,
            "capture": "auto",
        },
    )

    # Per-request custom instructions and categories
    if config.custom_instructions:
        add_kwargs["custom_instructions"] = config.custom_instructions
    if config.custom_categories:
        add_kwargs["custom_categories"] = config.custom_categories
    if includes or config.includes:
        add_kwargs["includes"] = includes or config.includes
    if excludes or config.excludes:
        add_kwargs["excludes"] = excludes or config.excludes

    # Session scoping
    if session_id:
        add_kwargs["run_id"] = session_id
        add_kwargs["metadata"]["session_id"] = session_id

    # Expiration
    if expiry_days is not None:
        expiry = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
        add_kwargs["expiration_date"] = expiry
    elif config.auto_capture_expiry_days is not None:
        expiry = (
            datetime.now() + timedelta(days=config.auto_capture_expiry_days)
        ).strftime("%Y-%m-%d")
        add_kwargs["expiration_date"] = expiry

    result = client.add(messages, **add_kwargs)
    return result


def handle_stop(hook_input: dict, config: ProjectConfig) -> Optional[dict]:
    """Handle Stop hook — main assistant auto-capture."""
    # Guard against infinite loops
    if hook_input.get("stop_hook_active"):
        return None

    return capture(
        hook_input,
        config,
        source="claude-code-stop",
        agent_id=config.agent_id_main,
        min_chars=config.capture_min_chars,
        user_content="[Session context for memory extraction]",
        includes="architectural decisions, implementation patterns, bug fixes, user preferences",
        excludes="raw code, API keys, recalled memories",
    )


def handle_subagent_stop(hook_input: dict, config: ProjectConfig) -> Optional[dict]:
    """Handle SubagentStop hook — subagent analysis capture."""
    return capture(
        hook_input,
        config,
        source="claude-code-subagent",
        agent_id=config.agent_id_subagent,
        min_chars=config.subagent_min_chars,
        user_content="[Subagent analysis for memory extraction]",
        includes="architectural decisions, implementation patterns, research findings, codebase analysis",
        excludes="raw code, API keys, recalled memories, file listings",
    )


def handle_pre_compact(hook_input: dict, config: ProjectConfig) -> Optional[dict]:
    """Handle PreCompact hook — ephemeral session preservation."""
    return capture(
        hook_input,
        config,
        source="pre-compact",
        agent_id=config.agent_id_main,
        min_chars=config.capture_min_chars,
        expiry_days=config.compact_expiry_days,
        user_content="[Pre-compaction context for memory extraction]",
    )


def handle_session_end(hook_input: dict, config: ProjectConfig) -> Optional[dict]:
    """Handle SessionEnd hook — final capture on Ctrl+C / session close."""
    return capture(
        hook_input,
        config,
        source="claude-code-session-end",
        agent_id=config.agent_id_main,
        min_chars=config.capture_min_chars,
        user_content="[End-of-session context for memory extraction]",
        includes="architectural decisions, implementation patterns, bug fixes, user preferences, session conclusions",
        excludes="raw code, API keys, recalled memories",
    )
