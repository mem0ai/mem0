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
# Value is one of: "KEEP_NEW", "KEEP_OLD", "DELETE_OLD", "MERGE", "FOLLOW_LLM".
# When set, hitl_prompt_* returns the stored resolution without prompting.
# "FOLLOW_LLM" re-reads cr.proposed_action each time (non-deterministic but prompt-free).
_session_overrides: dict[str, str] = {}

_ACTION_LABELS: dict[str, str] = {
    "KEEP_NEW":   "keep incoming, discard existing",
    "KEEP_OLD":   "keep existing, discard incoming",
    "DELETE_OLD": "delete existing, discard incoming (no new memory)",
    "MERGE":      "combine both memories into one",
}
_ALL_ACTIONS = ["KEEP_NEW", "KEEP_OLD", "DELETE_OLD", "MERGE"]
_ALWAYS_MAP: dict[str, str] = {
    "always:keep-new":   "KEEP_NEW",
    "always:keep-old":   "KEEP_OLD",
    "always:delete-old": "DELETE_OLD",
    "always:merge":      "MERGE",
    "always:follow-llm": "FOLLOW_LLM",
}

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


def _resolve_proposed(cr: ConflictResolution) -> str:
    """Normalize cr.proposed_action to a known action, falling back to KEEP_NEW."""
    proposed = (cr.proposed_action or "").strip().upper()
    return proposed if proposed in _ALL_ACTIONS else "KEEP_NEW"


def _parse_hitl_input(raw: str, cr: ConflictResolution) -> tuple:
    """
    Parse a HITL user input string.
    Returns (resolution, session_strategy_or_None).
    resolution is None when the input is invalid.

    Valid forms:
      "y"                   → accept LLM's proposed action
      "1" / "2" / "3"       → pick from the three alternatives
      Any of the above followed by " always:<strategy>" to also set a session override.
    """
    parts = raw.split()
    if not parts:
        return None, None

    action_part = parts[0]
    always_part = parts[1] if len(parts) > 1 else None

    proposed = _resolve_proposed(cr)
    alternatives = [a for a in _ALL_ACTIONS if a != proposed]

    if action_part == "y":
        resolution = proposed
    elif action_part in ("1", "2", "3") and int(action_part) - 1 < len(alternatives):
        resolution = alternatives[int(action_part) - 1]
    else:
        return None, None

    session_strategy = None
    if always_part:
        session_strategy = _ALWAYS_MAP.get(always_part)
        if session_strategy is None:
            print(f"  Warning: unrecognized strategy {always_part!r}. Valid: {', '.join(_ALWAYS_MAP)}")

    return resolution, session_strategy


def hitl_prompt_sync(cr: ConflictResolution, session_id: str) -> str:
    """
    Blocking stdin HITL prompt.
    Returns a resolution string: KEEP_NEW | KEEP_OLD | DELETE_OLD | MERGE.
    Applies session overrides if already set; stores new always:* choices.
    """
    if session_id in _session_overrides:
        override = _session_overrides[session_id]
        if override == "FOLLOW_LLM":
            return _resolve_proposed(cr)
        return override

    _print_hitl_block(cr)
    raw = input("> ").strip().lower()
    resolution, session_strategy = _parse_hitl_input(raw, cr)

    if resolution is None:
        print("  Invalid choice. Enter y, 1, 2, or 3 — optionally followed by always:<strategy>.")
        raw = input("> ").strip().lower()
        resolution, session_strategy = _parse_hitl_input(raw, cr)
        if resolution is None:
            resolution = "KEEP_OLD"

    if session_strategy:
        _session_overrides[session_id] = session_strategy

    return resolution


async def hitl_prompt_async(cr: ConflictResolution, session_id: str) -> str:
    """
    Non-blocking async HITL prompt. Offloads stdin read to a thread pool executor.
    Returns a resolution string: KEEP_NEW | KEEP_OLD | DELETE_OLD | MERGE.
    Same session-override logic as hitl_prompt_sync.
    """
    import asyncio

    if session_id in _session_overrides:
        override = _session_overrides[session_id]
        if override == "FOLLOW_LLM":
            return _resolve_proposed(cr)
        return override

    _print_hitl_block(cr)
    loop = asyncio.get_event_loop()

    raw = (await loop.run_in_executor(None, input, "> ")).strip().lower()
    resolution, session_strategy = _parse_hitl_input(raw, cr)

    if resolution is None:
        print("  Invalid choice. Enter y, 1, 2, or 3 — optionally followed by always:<strategy>.")
        raw = (await loop.run_in_executor(None, input, "> ")).strip().lower()
        resolution, session_strategy = _parse_hitl_input(raw, cr)
        if resolution is None:
            resolution = "KEEP_OLD"

    if session_strategy:
        _session_overrides[session_id] = session_strategy

    return resolution


def _print_hitl_block(cr: ConflictResolution) -> None:
    proposed = _resolve_proposed(cr)
    alternatives = [a for a in _ALL_ACTIONS if a != proposed]

    alt_lines = "\n".join(
        f"  [{i + 1}]  {action:<12}— {_ACTION_LABELS[action]}"
        for i, action in enumerate(alternatives)
    )
    always_options = " | ".join(_ALWAYS_MAP)

    print(
        f"\n┌─ Contradiction detected ──────────────────────────────┐\n"
        f"│ Existing:  {cr.old_memory_text}\n"
        f"│ Incoming:  {cr.new_fact}\n"
        f"│\n"
        f"│ {cr.explanation}\n"
        f"│\n"
        f"│ LLM proposed: {cr.proposed_action}\n"
        f"└────────────────────────────────────────────────────────┘\n"
        f"\n"
        f"  [y]  accept proposed → {proposed}  ({_ACTION_LABELS[proposed]})\n"
        f"{alt_lines}\n"
        f"\n"
        f"To apply a strategy to all future conflicts this session, append:\n"
        f"  {always_options}\n"
        f'\nExamples: "y"  "2"  "y always:follow-llm"  "1 always:keep-old"'
    )
