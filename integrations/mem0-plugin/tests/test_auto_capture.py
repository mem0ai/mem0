"""Tests for auto_capture.py transcript parsing and exchange extraction."""

from __future__ import annotations

import json
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


@pytest.fixture(autouse=True)
def _scripts_path():
    abs_scripts = os.path.abspath(SCRIPTS_DIR)
    if abs_scripts not in sys.path:
        sys.path.insert(0, abs_scripts)
    yield
    if abs_scripts in sys.path:
        sys.path.remove(abs_scripts)


def _make_transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    lines = []
    for entry in entries:
        lines.append(json.dumps(entry))
    path.write_text("\n".join(lines) + "\n")
    return str(path)


def _msg(role, content):
    return {"message": {"role": role, "content": content}}


class TestTailLines:
    def test_reads_last_n_lines(self, tmp_path):
        from auto_capture import tail_lines

        p = tmp_path / "test.txt"
        p.write_text("\n".join(f"line{i}" for i in range(100)) + "\n")
        result = tail_lines(str(p), 5)
        assert len(result) >= 5
        assert result[-1] == "line99"

    def test_empty_file(self, tmp_path):
        from auto_capture import tail_lines

        p = tmp_path / "empty.txt"
        p.write_text("")
        assert tail_lines(str(p), 10) == []

    def test_nonexistent_file(self):
        from auto_capture import tail_lines

        assert tail_lines("/nonexistent/path", 10) == []


class TestExtractRecentExchanges:
    def test_extracts_user_assistant_pairs(self):
        from auto_capture import extract_recent_exchanges

        lines = [
            json.dumps(_msg("user", "What is Python used for?" * 3)),
            json.dumps(_msg("assistant", "Python is used for many things." * 3)),
            json.dumps(_msg("user", "Tell me about web frameworks." * 3)),
            json.dumps(_msg("assistant", "Django and Flask are popular." * 3)),
        ]
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 4
        assert result[0]["role"] == "user"
        assert result[1]["role"] == "assistant"

    def test_skips_short_messages(self):
        from auto_capture import extract_recent_exchanges

        lines = [
            json.dumps(_msg("user", "ok")),
            json.dumps(_msg("assistant", "Sure, here is a detailed explanation." * 3)),
        ]
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 1
        assert result[0]["role"] == "assistant"

    def test_skips_compact_summaries(self):
        from auto_capture import extract_recent_exchanges

        lines = [
            json.dumps({"isCompactSummary": True, "message": {"role": "assistant", "content": "summary " * 20}}),
            json.dumps(_msg("user", "This is a real user message here." * 2)),
        ]
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 1
        assert result[0]["role"] == "user"

    def test_limits_to_max_exchanges(self):
        from auto_capture import extract_recent_exchanges

        lines = []
        for i in range(10):
            lines.append(json.dumps(_msg("user", f"Question number {i} with enough text to pass." * 2)))
            lines.append(json.dumps(_msg("assistant", f"Answer number {i} with enough text to pass." * 2)))
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 4

    def test_handles_list_content(self):
        from auto_capture import extract_recent_exchanges

        lines = [
            json.dumps({"message": {"role": "user", "content": [
                {"type": "text", "text": "This is block content that is long enough." * 2},
            ]}}),
        ]
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 1
        assert "block content" in result[0]["content"]

    def test_empty_lines(self):
        from auto_capture import extract_recent_exchanges

        assert extract_recent_exchanges([], max_exchanges=2) == []

    def test_truncates_long_content(self):
        from auto_capture import extract_recent_exchanges

        long_text = "x" * 5000
        lines = [json.dumps(_msg("user", long_text))]
        result = extract_recent_exchanges(lines, max_exchanges=1)
        assert len(result) == 1
        assert len(result[0]["content"]) == 2000

    def test_skips_tool_call_assistant_messages(self):
        from auto_capture import extract_recent_exchanges

        lines = [
            json.dumps(_msg("assistant", '{"tool_calls": [{"name": "read"}]}')),
            json.dumps(_msg("user", "Thanks for reading that file for me!" * 2)),
        ]
        result = extract_recent_exchanges(lines, max_exchanges=2)
        assert len(result) == 1
        assert result[0]["role"] == "user"
