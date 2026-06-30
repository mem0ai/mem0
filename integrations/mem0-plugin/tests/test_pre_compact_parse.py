"""Regression tests for on_pre_compact.parse_transcript transcript dialects.

Cursor agent transcripts mark turns with ``role`` instead of the Claude/Codex
``type``. The PreCompact/Stop fallback parser only matched on ``type``, so for
Cursor sessions it extracted no user messages and no assistant text, leaving the
safety-net capture empty.
"""

from __future__ import annotations

import json


def test_parse_transcript_claude_type_style():
    """Claude Code / Codex style entries use ``type``."""
    from on_pre_compact import parse_transcript

    lines = [
        json.dumps(
            {"type": "user", "message": {"content": "please refactor the parser module"}}
        ),
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Refactored the parser as requested."},
                        {
                            "type": "tool_use",
                            "name": "Edit",
                            "input": {"file_path": "parser.py"},
                        },
                    ]
                },
            }
        ),
    ]
    state = parse_transcript(lines)
    assert "please refactor the parser module" in state["user_messages"]
    assert state["last_assistant_text"] == "Refactored the parser as requested."
    assert "parser.py" in state["files_modified"]


def test_parse_transcript_cursor_role_style():
    """Cursor agent transcripts use ``role`` instead of ``type`` (issue #6006).

    Without the fix, parse_transcript skips every Cursor entry and returns
    empty user_messages / last_assistant_text.
    """
    from on_pre_compact import parse_transcript

    lines = [
        json.dumps(
            {"role": "user", "message": {"content": "please update the configuration"}}
        ),
        json.dumps(
            {
                "role": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "text",
                            "text": "I updated the requested configuration and verified it.",
                        }
                    ]
                },
            }
        ),
    ]
    state = parse_transcript(lines)
    assert "please update the configuration" in state["user_messages"]
    assert (
        state["last_assistant_text"]
        == "I updated the requested configuration and verified it."
    )


def test_parse_transcript_cursor_assistant_string_content():
    """Cursor assistant entry whose content is a bare string is captured."""
    from on_pre_compact import parse_transcript

    lines = [
        json.dumps({"role": "assistant", "message": {"content": "done, all green"}}),
    ]
    state = parse_transcript(lines)
    assert state["last_assistant_text"] == "done, all green"


def test_parse_transcript_ignores_other_roles():
    """Non user/assistant roles are still skipped."""
    from on_pre_compact import parse_transcript

    lines = [
        json.dumps({"role": "system", "message": {"content": "system config here"}}),
        json.dumps({"role": "tool", "message": {"content": "tool output"}}),
    ]
    state = parse_transcript(lines)
    assert state["user_messages"] == []
    assert state["last_assistant_text"] == ""
