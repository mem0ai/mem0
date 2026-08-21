"""Tests for _search.py — shared mem0 search API helper."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_search_memories_returns_results():
    from _search import search_memories

    fake_results = [
        {"id": "abc123", "memory": "Use Postgres for auth", "metadata": {"type": "decision"}},
        {"id": "def456", "memory": "Never use floats for money", "metadata": {"type": "anti_pattern"}},
    ]

    def mock_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": fake_results}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results = search_memories("test-key", "user1", "proj1", "auth decisions")

    assert len(results) == 2
    assert results[0]["id"] == "abc123"


def test_search_memories_with_metadata_type():
    from _search import search_memories

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("key", "user", "proj", "query", metadata_type="decision")

    filters = captured_body["filters"]
    assert {"metadata": {"type": "decision"}} in filters["AND"]


def test_search_memories_handles_api_error():
    from _search import search_memories

    with patch("urllib.request.urlopen", side_effect=Exception("timeout")):
        results = search_memories("key", "user", "proj", "query")

    assert results == []


def test_search_memories_handles_list_response():
    from _search import search_memories

    fake_results = [{"id": "abc", "memory": "test"}]

    def mock_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.read.return_value = json.dumps(fake_results).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results = search_memories("key", "user", "proj", "query")

    assert len(results) == 1


def test_search_memories_respects_top_k():
    from _search import search_memories

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("key", "user", "proj", "query", top_k=5)

    assert captured_body["top_k"] == 5


def test_search_memories_no_api_key_returns_empty():
    from _search import search_memories

    results = search_memories("", "user", "proj", "query")
    assert results == []


def test_search_memories_logs_rate_limit_error(capsys):
    """Bug bash #22: a 429 must not look identical to a genuine empty result."""
    from _search import search_memories

    def mock_urlopen(req, timeout=None):
        raise urllib.error.HTTPError("http://x", 429, "Too Many Requests", {}, None)

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results = search_memories("key", "user", "proj", "query")

    assert results == []
    err = capsys.readouterr().err
    assert "429" in err
    assert "Too Many Requests" in err


def test_search_memories_happy_path_is_silent(capsys):
    from _search import search_memories

    def mock_urlopen(req, timeout=None):
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        results = search_memories("key", "user", "proj", "query")

    assert results == []
    assert capsys.readouterr().err == ""


def test_search_memories_omits_rerank_by_default():
    """Regression for #5684: rerank must not be sent unless requested."""
    from _search import search_memories

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("key", "user", "proj", "query")

    assert "rerank" not in captured_body


def test_search_memories_forwards_rerank_true():
    """Regression for #5684: rerank=True must reach the request body so the
    REST endpoint actually reranks (it does not rerank when omitted)."""
    from _search import search_memories

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("key", "user", "proj", "query", rerank=True)

    assert captured_body.get("rerank") is True


def test_should_rerank_defaults_true(monkeypatch):
    """Regression for #5684: auto-injection reranks by default."""
    from _search import should_rerank

    monkeypatch.delenv("MEM0_RERANK", raising=False)
    assert should_rerank() is True


def test_should_rerank_opt_out_values(monkeypatch):
    from _search import should_rerank

    for falsey in ("0", "false", "False", "NO", "off", ""):
        monkeypatch.setenv("MEM0_RERANK", falsey)
        assert should_rerank() is False, falsey

    for truthy in ("1", "true", "yes", "on"):
        monkeypatch.setenv("MEM0_RERANK", truthy)
        assert should_rerank() is True, truthy


def test_format_results_for_context():
    from _search import format_results_for_context

    memories = [
        {"id": "abc12345-long-id", "memory": "Use Postgres for auth", "metadata": {"type": "decision"}},
        {"id": "def67890-long-id", "memory": "JWT tokens expire in 1h", "metadata": {"type": "convention"}},
    ]

    output = format_results_for_context(memories, heading="Relevant memories")
    assert "Relevant memories" in output
    assert "[decision]" in output
    assert "Use Postgres for auth" in output
    assert "abc12345" in output


def test_global_search_filters_are_positively_scoped():
    """Regression: the platform API rejects wildcard-only filters with
    "filters must include at least one positively-scoped entity ID", so the
    global_search path must anchor its OR with the caller's user_id.

    Scope note: this patches ``urllib.request.urlopen`` wholesale, so it proves the
    OUTGOING PAYLOAD SHAPE only — never that the platform accepts it. A green run here
    is not evidence the 400 is gone; that was confirmed separately with a live request.
    Treat this as a guard against the shape regressing, nothing more.
    """
    from _search import search_memories

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        search_memories("test-key", "user1", "proj1", "anything", global_search=True)

    clauses = captured_body["filters"]["OR"]
    assert {"user_id": "user1"} in clauses
    assert {"user_id": "*"} not in clauses


def test_global_search_filter_helper_is_the_single_definition():
    """Every caller must build the filter through one helper.

    The first pass at this fix patched three sites and missed a fourth
    (``on_session_start.sh``), which kept 400ing silently and showed ``memories=?``
    in the session banner. The helper exists so that class of miss is structurally
    impossible; this pins its shape.
    """
    from _identity import global_search_filter

    assert global_search_filter("user1") == {
        "OR": [{"user_id": "user1"}, {"agent_id": "*"}]
    }
    # The failure mode being guarded against.
    assert {"user_id": "*"} not in global_search_filter("user1")["OR"]


def test_session_timeline_uses_positively_scoped_global_filter():
    """session_timeline.py hits the list endpoint and had no coverage of its own."""
    import session_timeline

    captured_body = {}

    def mock_urlopen(req, timeout=None):
        captured_body.update(json.loads(req.data.decode()))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"results": []}).encode()
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch.dict(os.environ, {"MEM0_GLOBAL_SEARCH": "true"}), \
            patch("urllib.request.urlopen", side_effect=mock_urlopen):
        session_timeline.fetch_recent_memories("test-key", "user1", "proj1")

    clauses = captured_body["filters"]["OR"]
    assert {"user_id": "user1"} in clauses
    assert {"user_id": "*"} not in clauses


def test_on_session_start_banner_filter_is_positively_scoped():
    """The 4th site. It builds its filter in an inline python block inside a bash
    hook, so this runs that block's logic the same way the hook does."""
    import subprocess

    scripts_dir = Path(__file__).resolve().parent.parent / "scripts"
    code = (
        "import json, os, sys\n"
        "sys.path.insert(0, os.environ['PYTHONPATH'])\n"
        "from _identity import global_search_filter\n"
        "print(json.dumps(global_search_filter(os.environ['UID_IN'])))\n"
    )
    out = subprocess.run(
        [sys.executable, "-c", code],
        env={**os.environ, "PYTHONPATH": str(scripts_dir), "UID_IN": "user1"},
        capture_output=True, text=True, check=True,
    ).stdout

    clauses = json.loads(out)["OR"]
    assert {"user_id": "user1"} in clauses
    assert {"user_id": "*"} not in clauses
