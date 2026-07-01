"""Regression tests for capture_session_summary.py request body construction.

Guards against the double-JSON-encoding bug where ``files_touched`` was stored
as a pre-serialized JSON string and then encoded a second time with the rest of
the request body — surfacing as escaped, slash-heavy blobs in the memories shown
inside Claude Code / Cursor / Codex / Antigravity (all four editors share this
script).
"""

from __future__ import annotations

import json


class _FakeResp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _capture_request_body(monkeypatch):
    """Patch urlopen so store_summary posts nowhere; capture the request body."""
    import capture_session_summary as css

    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["raw"] = req.data.decode("utf-8")
        captured["body"] = json.loads(captured["raw"])
        return _FakeResp()

    monkeypatch.setattr(css.urllib.request, "urlopen", fake_urlopen)
    return captured, css


def test_files_touched_is_json_array_not_double_encoded(monkeypatch):
    """files_touched must be a real JSON array, encoded exactly once."""
    captured, css = _capture_request_body(monkeypatch)
    files = ["mem0/memory/main.py", "src/client/index.ts"]

    css.store_summary(
        api_key="test-key",
        summary_prompt="did some work",
        user_id="u1",
        session_id="s1",
        project_id="p1",
        branch="main",
        files=files,
    )

    files_touched = captured["body"]["metadata"]["files_touched"]
    assert isinstance(files_touched, list), (
        "files_touched must be a JSON array, not a double-encoded string; "
        f"got {type(files_touched).__name__}: {files_touched!r}"
    )
    assert files_touched == files
    # The file paths must not appear as an escaped JSON string inside the body.
    assert '\\"' not in captured["raw"]


def test_files_touched_omitted_when_no_files(monkeypatch):
    """No files touched -> no files_touched key (unchanged behaviour)."""
    captured, css = _capture_request_body(monkeypatch)

    css.store_summary(
        api_key="test-key",
        summary_prompt="did some work",
        user_id="u1",
        session_id="s1",
        project_id="p1",
        branch="main",
        files=[],
    )

    assert "files_touched" not in captured["body"]["metadata"]


def test_extract_assistant_message_claude_type_style():
    """Claude Code / Codex style entries use ``type == 'assistant'``."""
    import capture_session_summary as css

    line = json.dumps(
        {
            "type": "assistant",
            "message": {"content": [{"type": "text", "text": "Claude finished the task."}]},
        }
    )
    assert css.extract_last_assistant_message([line]) == "Claude finished the task."


def test_extract_assistant_message_cursor_role_style():
    """Cursor agent transcripts use ``role == 'assistant'`` (issue #6006).

    Without the fix this returns "" because the parser only checked ``type``,
    so the stop hook logs "Assistant message too short (0 chars)" and skips
    storing the session summary.
    """
    import capture_session_summary as css

    line = json.dumps(
        {
            "role": "assistant",
            "message": {
                "content": [
                    {
                        "type": "text",
                        "text": "I completed the requested change and verified the result.",
                    }
                ]
            },
        }
    )
    assert (
        css.extract_last_assistant_message([line])
        == "I completed the requested change and verified the result."
    )


def test_extract_assistant_message_cursor_string_content():
    """Cursor entry whose content is a bare string is returned verbatim."""
    import capture_session_summary as css

    line = json.dumps({"role": "assistant", "message": {"content": "plain string reply"}})
    assert css.extract_last_assistant_message([line]) == "plain string reply"


def test_extract_assistant_message_returns_latest_turn():
    """The most recent assistant entry wins, across mixed dialects."""
    import capture_session_summary as css

    lines = [
        json.dumps(
            {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}}
        ),
        json.dumps({"role": "user", "message": {"content": "do more"}}),
        json.dumps({"role": "assistant", "message": {"content": "second"}}),
    ]
    assert css.extract_last_assistant_message(lines) == "second"


def test_extract_assistant_message_ignores_non_assistant_role():
    """User/system entries must not be mistaken for assistant messages."""
    import capture_session_summary as css

    lines = [
        json.dumps({"role": "user", "message": {"content": "talk about the assistant"}}),
        json.dumps({"role": "system", "message": {"content": "assistant config"}}),
    ]
    assert css.extract_last_assistant_message(lines) == ""
