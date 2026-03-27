"""Tests for output formatting."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from mem0_cli.output import (
    format_add_result,
    format_memories_table,
    format_memories_text,
    format_single_memory,
)


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    return Console(file=buf, force_terminal=False, no_color=True, width=120, highlight=False), buf


SAMPLE_MEMORIES = [
    {
        "id": "abc-123-def-456",
        "memory": "User prefers dark mode",
        "score": 0.92,
        "created_at": "2026-02-15T10:30:00Z",
        "categories": ["preferences"],
    },
    {
        "id": "ghi-789-jkl-012",
        "memory": "User uses vim keybindings",
        "score": 0.78,
        "created_at": "2026-03-01T14:00:00Z",
        "categories": ["tools"],
    },
]


class TestTextFormat:
    def test_format_memories_text(self):
        console, buf = _make_console()
        format_memories_text(console, SAMPLE_MEMORIES)
        output = buf.getvalue()
        assert "Found 2 memories" in output
        assert "dark mode" in output
        assert "vim keybindings" in output
        assert "0.92" in output

    def test_format_memories_text_empty(self):
        console, buf = _make_console()
        format_memories_text(console, [])
        output = buf.getvalue()
        assert "Found 0" in output


class TestTableFormat:
    def test_format_memories_table(self):
        console, buf = _make_console()
        format_memories_table(console, SAMPLE_MEMORIES)
        output = buf.getvalue()
        assert "dark mode" in output
        assert "abc-123-" in output

    def test_format_memories_table_empty(self):
        console, buf = _make_console()
        format_memories_table(console, [])
        output = buf.getvalue()
        # Should still render (empty table)
        assert "ID" in output


class TestSingleMemory:
    def test_format_single_memory_text(self):
        console, buf = _make_console()
        mem = SAMPLE_MEMORIES[0]
        format_single_memory(console, mem, "text")
        output = buf.getvalue()
        assert "dark mode" in output
        assert "abc-123-def-456" in output

    def test_format_single_memory_json(self):
        console, buf = _make_console()
        mem = SAMPLE_MEMORIES[0]
        format_single_memory(console, mem, "json")
        output = buf.getvalue()
        assert '"memory"' in output


class TestAddResult:
    def test_format_add_result_text(self):
        console, buf = _make_console()
        result = {
            "results": [
                {"id": "abc-123-def-456", "memory": "User prefers dark mode", "event": "ADD"},
            ]
        }
        format_add_result(console, result, "text")
        output = buf.getvalue()
        assert "dark mode" in output
        assert "Added" in output

    def test_format_add_result_update_event(self):
        console, buf = _make_console()
        result = {
            "results": [
                {"id": "abc-123", "memory": "Updated pref", "event": "UPDATE"},
            ]
        }
        format_add_result(console, result, "text")
        output = buf.getvalue()
        assert "Updated" in output

    def test_format_add_result_noop(self):
        console, buf = _make_console()
        result = {
            "results": [
                {"id": "abc-123", "memory": "Same thing", "event": "NOOP"},
            ]
        }
        format_add_result(console, result, "text")
        output = buf.getvalue()
        assert "No change" in output

    def test_format_add_result_quiet(self):
        console, buf = _make_console()
        result = {"results": [{"id": "abc-123", "memory": "Quiet", "event": "ADD"}]}
        format_add_result(console, result, "quiet")
        output = buf.getvalue()
        assert output.strip() == ""

    def test_format_add_result_empty(self):
        console, buf = _make_console()
        format_add_result(console, {"results": []}, "text")
        output = buf.getvalue()
        assert "No memories extracted" in output
