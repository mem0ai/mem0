"""Recall engine for Claude Code hooks.

Provides dual-scope search (long-term + session), graph relations,
tagged context formatting, and smart prompt filtering.

Used by UserPromptSubmit, SessionStart, and SubagentStart hooks.
"""

import os
from typing import List, Optional, Tuple

from .client import get_client
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


def search_dual_scope(
    client,
    query: str,
    config: ProjectConfig,
    session_id: Optional[str] = None,
    top_k: int = 5,
    session_top_k: int = 3,
) -> Tuple[List[dict], List[dict], List[dict]]:
    """Search both long-term (user-scoped) and session-scoped memories.

    Returns (long_term_items, session_items, relations).
    """
    # Long-term memories (user + app scoped)
    long_term = client.search(
        query,
        keyword_search=True,
        rerank=True,
        filter_memories=True,
        top_k=top_k,
        enable_graph=True,
        filters={"AND": [{"user_id": config.user_id}, {"app_id": config.app_id}]},
    )

    # Normalize response format
    if isinstance(long_term, dict):
        lt_items = long_term.get("results", [])
        relations = long_term.get("relations", [])
    elif isinstance(long_term, list):
        lt_items = long_term
        relations = []
    else:
        lt_items = []
        relations = []

    # Session memories (run_id scoped) — only if session_id available
    session_items = []
    if session_id:
        try:
            session_results = client.search(
                query,
                keyword_search=True,
                top_k=session_top_k,
                filters={
                    "AND": [
                        {"user_id": config.user_id},
                        {"run_id": session_id},
                    ]
                },
            )
            if isinstance(session_results, dict):
                session_items = session_results.get("results", [])
            elif isinstance(session_results, list):
                session_items = session_results
        except Exception:
            pass  # Session search is best-effort

    # Deduplicate by memory ID
    seen_ids = set()
    deduped_lt = []
    for mem in lt_items:
        mid = mem.get("id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            deduped_lt.append(mem)
        elif not mid:
            deduped_lt.append(mem)

    deduped_session = []
    for mem in session_items:
        mid = mem.get("id")
        if mid and mid not in seen_ids:
            seen_ids.add(mid)
            deduped_session.append(mem)
        elif not mid:
            deduped_session.append(mem)

    return deduped_lt, deduped_session, relations


def format_context(
    lt_items: List[dict],
    session_items: List[dict],
    relations: List[dict],
) -> str:
    """Format memories into tagged context for easy stripping.

    Uses <recalled-memories> XML tags so the capture hook can
    strip them before sending to mem0 (prevents feedback loops).
    """
    lines = ["<recalled-memories>"]

    if lt_items:
        lines.append("Long-term:")
        for mem in lt_items:
            memory_text = mem.get("memory", "")
            categories = mem.get("categories", [])
            cat_str = f" [{', '.join(categories)}]" if categories else ""
            lines.append(f"- {memory_text}{cat_str}")

    if session_items:
        lines.append("")
        lines.append("Session:")
        for mem in session_items:
            memory_text = mem.get("memory", "")
            lines.append(f"- {memory_text}")

    if relations:
        lines.append("")
        lines.append("Relations:")
        for rel in relations:
            source = rel.get("source", "?")
            relationship = rel.get("relationship", "?")
            target = rel.get("target", "?")
            lines.append(f"- {source} -> {relationship} -> {target}")

    lines.append("</recalled-memories>")
    return "\n".join(lines)


def _should_skip_prompt(prompt: str, config: ProjectConfig) -> bool:
    """Check if a prompt should be skipped for recall."""
    if not prompt or len(prompt) < 10:
        return True
    if prompt.startswith("/"):
        return True
    if prompt.lower() in config.skip_prompts:
        return True
    return False


def recall(
    hook_input: dict,
    config: ProjectConfig,
) -> Optional[str]:
    """Core recall logic for UserPromptSubmit.

    Returns formatted context string or None if nothing found / skipped.
    """
    query = hook_input.get("prompt", "").strip()
    if _should_skip_prompt(query, config):
        return None

    session_id = _extract_session_id(hook_input)

    client = get_client()
    if not client:
        return None

    lt_items, session_items, relations = search_dual_scope(
        client,
        query,
        config,
        session_id=session_id,
        top_k=config.recall_top_k,
        session_top_k=config.session_recall_top_k,
    )

    if not lt_items and not session_items:
        return None

    return format_context(lt_items, session_items, relations)


def recall_session_start(
    hook_input: dict,
    config: ProjectConfig,
) -> Optional[str]:
    """Recall for SessionStart hook with source-differentiated queries.

    SessionStart sources:
      - startup: Broad project recall
      - resume: Session context + project basics
      - compact: Key architectural facts to rebuild context
    """
    source = hook_input.get("session_source", "startup")

    if source == "resume":
        query = "recent session context architecture decisions implementation"
        top_k = 8
    elif source == "compact":
        query = "key architectural facts implementation patterns conventions"
        top_k = config.startup_top_k
    else:  # startup
        query = "architecture implementation status decisions patterns conventions"
        top_k = config.startup_top_k

    session_id = _extract_session_id(hook_input)

    client = get_client()
    if not client:
        return None

    lt_items, session_items, relations = search_dual_scope(
        client,
        query,
        config,
        session_id=session_id,
        top_k=top_k,
        session_top_k=config.session_recall_top_k,
    )

    if not lt_items and not session_items:
        return None

    return format_context(lt_items, session_items, relations)


def recall_subagent_start(
    hook_input: dict,
    config: ProjectConfig,
) -> Optional[str]:
    """Recall for SubagentStart hook — inject relevant context into subagents.

    Uses the subagent's task description as the search query.
    """
    # SubagentStart provides the subagent's prompt/description
    query = hook_input.get("prompt", "").strip()
    if not query or len(query) < 10:
        return None

    session_id = _extract_session_id(hook_input)

    client = get_client()
    if not client:
        return None

    lt_items, session_items, relations = search_dual_scope(
        client,
        query,
        config,
        session_id=session_id,
        top_k=config.recall_top_k,
        session_top_k=config.session_recall_top_k,
    )

    if not lt_items and not session_items:
        return None

    return format_context(lt_items, session_items, relations)
