"""Regression tests: assistant-authored text must never be posted as role="user".

The Stop hook (capture_session_summary) and the post-compact hook
(capture_compact_summary) both ship *model-authored* prose to
POST /v3/memories/add/. Mem0's fact extractor renders each message as
"{role}: {content}" and is instructed to extract "facts and preferences about
the user" — so role is the only signal separating what the human said from what
Claude said.

Posting Claude's own words under role="user" made the extractor read Claude's
first-person prose ("I recommend pgvector", "I found the bug in auth.py") as the
*human's* statements and store them under their user_id. The Stop hook fires on
every assistant turn, so this corrupted memory on nearly every message.
"""

from __future__ import annotations

import json


class _FakeResp:
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def _capture(monkeypatch, module):
    """Patch urlopen so store_summary posts nowhere; capture the request body."""
    captured: dict = {}

    def fake_urlopen(req, timeout=0):
        captured["body"] = json.loads(req.data.decode("utf-8"))
        return _FakeResp()

    monkeypatch.setattr(module.urllib.request, "urlopen", fake_urlopen)
    return captured


# Claude's own voice — first-person prose that must never be attributed to the human.
ASSISTANT_PROSE = (
    "I traced the root cause to auth.py and I recommend we switch to pgvector "
    "for the vector store. I'll refactor the session handler next."
)


def test_session_summary_posts_assistant_prose_as_assistant(monkeypatch):
    """Stop hook: the last assistant message must be tagged role="assistant"."""
    import capture_session_summary as css

    captured = _capture(monkeypatch, css)

    css.store_summary(
        api_key="test-key",
        summary_prompt=css.build_summary_prompt(ASSISTANT_PROSE, []),
        user_id="u1",
        session_id="s1",
        project_id="p1",
        branch="main",
        files=[],
    )

    messages = captured["body"]["messages"]
    for msg in messages:
        if ASSISTANT_PROSE in msg["content"]:
            assert msg["role"] == "assistant", (
                "Claude's own words were posted as role='user' — mem0 will extract "
                "them as facts about the human. Got role=%r" % msg["role"]
            )
            break
    else:
        raise AssertionError("assistant prose never made it into the payload")


def test_compact_summary_posts_assistant_prose_as_assistant(monkeypatch):
    """Post-compact hook: the compact summary is model-authored, not user-authored."""
    import capture_compact_summary as ccs

    captured = _capture(monkeypatch, ccs)

    ccs.store_summary(
        api_key="test-key",
        summary=ASSISTANT_PROSE,
        user_id="u1",
        session_id="s1",
        project_id="p1",
        branch="main",
    )

    messages = captured["body"]["messages"]
    for msg in messages:
        if ASSISTANT_PROSE in msg["content"]:
            assert msg["role"] == "assistant", (
                "Compact summary (written by Claude) was posted as role='user'. Got role=%r" % msg["role"]
            )
            break
    else:
        raise AssertionError("assistant prose never made it into the payload")


def test_no_user_role_message_carries_assistant_prose(monkeypatch):
    """Belt and braces: no user-role message may contain the assistant's words."""
    import capture_session_summary as css

    captured = _capture(monkeypatch, css)

    css.store_summary(
        api_key="test-key",
        summary_prompt=css.build_summary_prompt(ASSISTANT_PROSE, ["auth.py"]),
        user_id="u1",
        session_id="s1",
        project_id="p1",
        branch="main",
        files=["auth.py"],
    )

    for msg in captured["body"]["messages"]:
        if msg["role"] == "user":
            assert ASSISTANT_PROSE not in msg["content"], (
                "A user-role message carries Claude's prose — this is the misattribution bug."
            )


def test_auto_capture_preserves_real_roles():
    """auto_capture is the reference: it must pass roles through untouched."""
    import auto_capture

    lines = [
        json.dumps({"type": "user", "message": {"role": "user", "content": "why is the build failing on main?"}}),
        json.dumps(
            {
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": ASSISTANT_PROSE}]},
            }
        ),
    ]

    messages = auto_capture.extract_recent_exchanges(lines)

    assert [m["role"] for m in messages] == ["user", "assistant"]
    assert ASSISTANT_PROSE in messages[1]["content"]
