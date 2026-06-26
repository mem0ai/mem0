"""Tests for _search.py — shared mem0 search API helper."""

from __future__ import annotations

import json
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
