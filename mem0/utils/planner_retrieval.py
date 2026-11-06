import re
from typing import Any, Mapping, Sequence


_WORD_RE = re.compile(r"[A-Za-z0-9_]+")
_PROCEDURAL_TERMS = {
    "avoid",
    "choose",
    "error",
    "fail",
    "failure",
    "fix",
    "plan",
    "prefer",
    "retry",
    "step",
    "tool",
    "workflow",
}


def _clean_items(items: Sequence[str] | None) -> list[str]:
    if not items:
        return []
    return [item.strip() for item in items if isinstance(item, str) and item.strip()]


def build_planner_query(
    user_goal: str,
    plan: Sequence[str] | None = None,
    current_step: str | None = None,
    tools: Sequence[str] | None = None,
    previous_failures: Sequence[str] | None = None,
) -> str:
    """Build a retrieval query for planner-executor agent workflows."""
    goal = user_goal.strip()
    if not goal:
        raise ValueError("user_goal must be a non-empty string")

    sections = [f"User goal: {goal}"]

    plan_items = _clean_items(plan)
    if plan_items:
        plan_text = "\n".join(f"{index}. {item}" for index, item in enumerate(plan_items, start=1))
        sections.append(f"Plan:\n{plan_text}")

    if current_step and current_step.strip():
        sections.append(f"Current step: {current_step.strip()}")

    tool_items = _clean_items(tools)
    if tool_items:
        sections.append(f"Available tools: {', '.join(tool_items)}")

    failure_items = _clean_items(previous_failures)
    if failure_items:
        failure_text = "\n".join(f"- {item}" for item in failure_items)
        sections.append(f"Previous failures or lessons:\n{failure_text}")

    sections.append(
        "Retrieve memories that help choose the next action, reuse procedural experience, "
        "avoid repeated failures, and select appropriate tools."
    )
    return "\n\n".join(sections)


def _tokens(text: str) -> set[str]:
    return {match.group(0).lower() for match in _WORD_RE.finditer(text)}


def _memory_text(memory: Mapping[str, Any]) -> str:
    parts = []
    for key in ("memory", "text", "content", "data"):
        value = memory.get(key)
        if isinstance(value, str):
            parts.append(value)

    metadata = memory.get("metadata")
    if isinstance(metadata, Mapping):
        for value in metadata.values():
            if isinstance(value, str):
                parts.append(value)

    return " ".join(parts)


def rerank_plan_memories(
    memories: Sequence[Mapping[str, Any]],
    user_goal: str,
    current_step: str | None = None,
    tools: Sequence[str] | None = None,
    limit: int = 5,
) -> list[Mapping[str, Any]]:
    """Rank memory candidates using planning-oriented lexical signals."""
    if limit <= 0:
        return []

    goal_terms = _tokens(user_goal)
    step_terms = _tokens(current_step or "")
    tool_terms = _tokens(" ".join(_clean_items(tools)))

    def score(memory: Mapping[str, Any]) -> float:
        text_terms = _tokens(_memory_text(memory))
        semantic_score = memory.get("score", 0)
        base_score = semantic_score if isinstance(semantic_score, (int, float)) else 0
        return (
            float(base_score)
            + len(text_terms & goal_terms) * 1.0
            + len(text_terms & step_terms) * 2.0
            + len(text_terms & tool_terms) * 2.5
            + len(text_terms & _PROCEDURAL_TERMS) * 0.5
        )

    ranked = sorted(enumerate(memories), key=lambda item: (-score(item[1]), item[0]))
    return [memory for _, memory in ranked[:limit]]
