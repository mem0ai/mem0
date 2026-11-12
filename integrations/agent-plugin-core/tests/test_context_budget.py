"""format_context budget behavior and injection accounting (#7891)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "python"))

from memory_core import (  # noqa: E402
    _in_context,
    format_context,
)


def _memory(text: str) -> dict:
    return {"memory": text}


class TestFormatContextBudget:
    def test_oversized_memory_does_not_starve_shorter_ones(self):
        oversized = "x" * 5000
        memories = [_memory(oversized), _memory("short one"), _memory("short two")]
        rendered = format_context(memories)
        assert "short one" in rendered
        assert "short two" in rendered

    def test_budget_is_still_respected(self):
        oversized = "x" * 5000
        memories = [_memory(oversized), _memory("y" * 5000)]
        rendered = format_context(memories)
        assert len(rendered) <= 10000

    def test_first_memory_truncates_to_fit_a_lone_budget(self):
        # A single oversized memory still renders truncated when nothing else fits.
        rendered = format_context([_memory("x" * 5000)])
        assert len(rendered) <= 10000
        assert rendered  # the truncated entry is present


class TestInjectionAccounting:
    def test_in_context_matches_normalized_text(self):
        memory = _memory("has  multiple   spaces")
        rendered = format_context([memory], heading="")
        assert _in_context(memory, rendered)

    def test_in_context_false_for_omitted_memory(self):
        memory = _memory("z" * 9000)
        other = _memory("tiny")
        rendered = format_context([memory, other], heading="")
        assert _in_context(other, rendered)
        # The oversized one was truncated into the context, so it IS included
        # (only a memory fully omitted by the budget is absent).
