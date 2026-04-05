"""
Conflict detection and resolution types and logic for mem0.

This module is intentionally free of imports from mem0.memory.main to avoid
circular imports. All business logic lives in pure functions; ConflictResolution
is a plain dataclass.
"""
import json
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, Optional

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

ConflictClass = Literal["CONTRADICTION", "NUANCE", "UPDATE", "NONE"]

# Module-level session overrides keyed by session_id.
# "always-replace" → resolve all subsequent CONTRADICTION as KEEP_NEW without prompting.
# "always-keep"    → resolve all subsequent CONTRADICTION as KEEP_OLD without prompting.
_session_overrides: dict[str, str] = {}

MERGE_PROMPT = (
    "You are a memory consolidation assistant. "
    "You will be given two statements about the same subject that partially contradict each other. "
    "Write a single, unified statement that preserves the most accurate and specific information "
    "from both. Return ONLY valid JSON with a single key 'merged': the unified statement. "
    "No preamble, no markdown fences."
)


@dataclass
class ConflictResolution:
    new_fact: str
    old_memory_id: str
    old_memory_text: str
    conflict_class: str  # ConflictClass
    explanation: str
    proposed_action: str  # "KEEP_NEW" | "KEEP_OLD" | "MERGE" | "DELETE_OLD"
    confidence_new: float
    confidence_old: float
    auto_resolved: bool
    resolution: str  # "KEEP_NEW" | "KEEP_OLD" | "MERGE" | "DELETE_OLD" | "SKIP" (SKIP = unresolved sentinel)
    merged_text: Optional[str]


def _execute_merge_llm_call(cr: ConflictResolution, llm) -> str:
    """
    Call the LLM to produce a unified statement merging old_memory_text and new_fact.
    Uses the same model and prompt format (system + user messages, json_object response_format)
    as the classification call.

    Falls back to [MERGE PENDING] placeholder on any failure.
    """
    messages = [
        {"role": "system", "content": MERGE_PROMPT},
        {
            "role": "user",
            "content": (
                f"Statement A (existing memory): {cr.old_memory_text}\n"
                f"Statement B (new fact): {cr.new_fact}\n\n"
                "Return JSON: {\"merged\": \"<unified statement>\"}"
            ),
        },
    ]
    try:
        response = llm.generate_response(messages=messages, response_format={"type": "json_object"})
        parsed = json.loads(response)
        merged = parsed.get("merged", "").strip()
        if not merged:
            raise ValueError("Empty 'merged' field in LLM response")
        return merged
    except Exception as e:
        logger.error(f"Merge LLM call failed: {e}. Using placeholder.")
        return f"[MERGE PENDING] {cr.old_memory_text} / {cr.new_fact}"


def apply_auto_resolution(cr: ConflictResolution, strategy: str) -> ConflictResolution:
    """
    Pure function. Returns a new ConflictResolution with auto_resolved=True and
    resolution set according to strategy. The llm argument is only used for "merge".

    NOTE: The caller is responsible for calling _execute_merge_llm_call and setting
    merged_text before or after calling this function when strategy == "merge".
    This function sets resolution="MERGE" and leaves merged_text as-is so the
    caller can populate it.
    """
    from dataclasses import replace  # local import to avoid top-level dep

    if strategy == "keep-higher-confidence":
        resolution = "KEEP_NEW" if cr.confidence_new >= cr.confidence_old else "KEEP_OLD"
    elif strategy == "keep-newer":
        resolution = "KEEP_NEW"
    elif strategy == "merge":
        resolution = "MERGE"
    elif strategy == "delete-old":
        resolution = "DELETE_OLD"
    elif strategy == "follow-llm":
        proposed_action = cr.proposed_action.strip().upper()
        if proposed_action == "KEEP_NEW":
            resolution = "KEEP_NEW"
        elif proposed_action == "KEEP_OLD":
            resolution = "KEEP_OLD"
        elif proposed_action == "DELETE_OLD":
            resolution = "DELETE_OLD"
        elif proposed_action == "MERGE":
            resolution = "MERGE"
        else:
            resolution = "KEEP_NEW"
            logger.error(f"Cannot identify proposed action: {proposed_action}. Using KEEP NEW as default")
    else:
        raise ValueError(f"Unknown auto_resolve_strategy: {strategy!r}")

    return replace(cr, auto_resolved=True, resolution=resolution)


def hitl_prompt_sync(cr: ConflictResolution, session_id: str) -> str:
    """
    Blocking stdin HITL prompt. Prints a formatted block and waits for user input.
    Returns one of: "y", "n", "always-replace", "always-keep".
    Applies session overrides if already set; stores new "always-*" choices.
    """
    if session_id in _session_overrides:
        return _session_overrides[session_id]

    _print_hitl_block(cr)
    choice = input("> ").strip().lower()
    if choice not in ("y", "n", "always-replace", "always-keep"):
        print("Invalid choice. Please enter y, n, always-replace, or always-keep.")
        choice = input("> ").strip().lower()
        if choice not in ("y", "n", "always-replace", "always-keep"):
            choice = "n"

    if choice in ("always-replace", "always-keep"):
        _session_overrides[session_id] = choice

    return choice


async def hitl_prompt_async(cr: ConflictResolution, session_id: str) -> str:
    """
    Non-blocking async HITL prompt. Offloads stdin read to a thread pool executor.
    Same logic and return values as hitl_prompt_sync.
    """
    import asyncio

    if session_id in _session_overrides:
        return _session_overrides[session_id]

    _print_hitl_block(cr)

    loop = asyncio.get_event_loop()
    choice = (await loop.run_in_executor(None, input, "> ")).strip().lower()
    if choice not in ("y", "n", "always-replace", "always-keep"):
        print("Invalid choice. Please enter y, n, always-replace, or always-keep.")
        choice = (await loop.run_in_executor(None, input, "> ")).strip().lower()
        if choice not in ("y", "n", "always-replace", "always-keep"):
            choice = "n"

    if choice in ("always-replace", "always-keep"):
        _session_overrides[session_id] = choice

    return choice


def _print_hitl_block(cr: ConflictResolution) -> None:
    print(
        f"\n┌─ Contradiction detected ──────────────────────────────┐\n"
        f"│ Existing:  {cr.old_memory_text}\n"
        f"│ Incoming:  {cr.new_fact}\n"
        f"│\n"
        f"│ Classification: CONTRADICTION\n"
        f"│ {cr.explanation}\n"
        f"│\n"
        f"│ Proposed action: {cr.proposed_action}\n"
        f"└────────────────────────────────────────────────────────┘\n"
        f"Choose: [y] accept proposed  [n] keep existing\n"
        f"        [always-replace] replace all subsequent contradictions this session\n"
        f"        [always-keep]    keep all subsequent contradictions this session"
    )
