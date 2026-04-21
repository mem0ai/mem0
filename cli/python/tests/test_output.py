"""Tests for output formatting."""

from __future__ import annotations

from io import StringIO

from rich.console import Console

from mem0_cli.output import (
    format_add_result,
    format_memories_table,
    format_memories_text,
    format_single_memory,
    sanitize_agent_data,
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

    def test_format_add_result_deduplicates_pending_by_event_id(self):
        console, buf = _make_console()
        result = {
            "results": [
                {"status": "PENDING", "event_id": "evt-dup"},
                {"status": "PENDING", "event_id": "evt-dup"},
            ]
        }
        format_add_result(console, result, "text")
        output = buf.getvalue()
        # Should show only one PENDING block despite two entries with same event_id
        assert output.count("evt-dup") == 2  # event_id line + status hint line
        assert output.count("Queued") == 1

    def test_format_add_result_empty(self):
        console, buf = _make_console()
        format_add_result(console, {"results": []}, "text")
        output = buf.getvalue()
        assert "No memories extracted" in output


class TestSanitizeAgentData:
    def test_add_projects_fields(self):
        raw = [
            {
                "id": "abc",
                "memory": "test",
                "event": "ADD",
                "metadata": {"x": 1},
                "categories": ["a"],
            }
        ]
        result = sanitize_agent_data("add", raw)
        assert result == [{"id": "abc", "memory": "test", "event": "ADD"}]

    def test_add_pending_passthrough(self):
        raw = [{"status": "PENDING", "event_id": "evt-123", "metadata": "noise"}]
        result = sanitize_agent_data("add", raw)
        assert result == [{"status": "PENDING", "event_id": "evt-123"}]

    def test_search_projects_fields(self):
        raw = [
            {
                "id": "abc",
                "memory": "test",
                "score": 0.9,
                "created_at": "2026-01-01",
                "categories": ["a"],
                "user_id": "u1",
                "agent_id": None,
            }
        ]
        result = sanitize_agent_data("search", raw)
        assert result == [
            {
                "id": "abc",
                "memory": "test",
                "score": 0.9,
                "created_at": "2026-01-01",
                "categories": ["a"],
            }
        ]

    def test_list_projects_fields(self):
        raw = [
            {
                "id": "abc",
                "memory": "test",
                "created_at": "2026-01-01",
                "categories": ["a"],
                "user_id": "u1",
            }
        ]
        result = sanitize_agent_data("list", raw)
        assert result == [
            {"id": "abc", "memory": "test", "created_at": "2026-01-01", "categories": ["a"]}
        ]

    def test_get_projects_fields(self):
        raw = {
            "id": "abc",
            "memory": "test",
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
            "categories": ["a"],
            "metadata": {"k": "v"},
            "user_id": "u1",
        }
        result = sanitize_agent_data("get", raw)
        assert "user_id" not in result
        assert "id" in result and "memory" in result

    def test_update_projects_fields(self):
        raw = {"id": "abc", "memory": "updated", "extra": "noise"}
        result = sanitize_agent_data("update", raw)
        assert result == {"id": "abc", "memory": "updated"}

    def test_event_list_projects_fields(self):
        raw = [
            {
                "id": "evt-1",
                "event_type": "ADD",
                "status": "SUCCEEDED",
                "graph_status": None,
                "latency": 100.0,
                "created_at": "2026-01-01",
                "updated_at": "2026-01-02",
            }
        ]
        result = sanitize_agent_data("event list", raw)
        assert result == [
            {
                "id": "evt-1",
                "event_type": "ADD",
                "status": "SUCCEEDED",
                "latency": 100.0,
                "created_at": "2026-01-01",
            }
        ]
        assert "updated_at" not in result[0]
        assert "graph_status" not in result[0]

    def test_event_status_flattens_results(self):
        raw = {
            "id": "evt-1",
            "event_type": "ADD",
            "status": "SUCCEEDED",
            "latency": 100.0,
            "created_at": "2026-01-01",
            "updated_at": "2026-01-02",
            "results": [
                {"id": "mem-1", "event": "ADD", "user_id": "alice", "data": {"memory": "dark mode"}}
            ],
        }
        result = sanitize_agent_data("event status", raw)
        assert result["results"][0] == {
            "id": "mem-1",
            "event": "ADD",
            "user_id": "alice",
            "memory": "dark mode",
        }
        assert "data" not in result["results"][0]

    def test_passthrough_commands(self):
        for cmd in ("status", "import", "config show", "config get", "config set"):
            data = {"key": "value", "other": "stuff"}
            assert sanitize_agent_data(cmd, data) == data

    def test_none_data(self):
        assert sanitize_agent_data("add", None) is None
