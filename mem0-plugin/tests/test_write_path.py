"""Tests for write-path app_id migration.

Verifies that all scripts writing to the Mem0 API:
1. Pass app_id as a top-level parameter (not in metadata)
2. Do NOT include project_id in metadata
3. Include branch in metadata when available
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch


def test_auto_import_post_memory_uses_app_id():
    """auto_import.post_memory sends app_id top-level, not metadata.project_id."""
    from auto_import import post_memory

    captured = {}

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        captured.update(body)
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        result = post_memory(
            api_key="test-key",
            content="test content",
            user_id="testuser",
            filename="CLAUDE.md",
            project_id="my-project",
            branch="main",
        )

    assert result is True
    assert captured["app_id"] == "my-project"
    assert captured["user_id"] == "testuser"
    assert "project_id" not in captured.get("metadata", {})
    assert captured["metadata"]["type"] == "project_profile"
    assert captured["metadata"]["branch"] == "main"
    assert captured["infer"] is False


def test_auto_import_post_memory_omits_empty_branch():
    """auto_import.post_memory skips branch in metadata when empty."""
    from auto_import import post_memory

    captured = {}

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        captured.update(body)
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        post_memory("key", "content", "user", "FILE.md", "proj", branch="")

    assert "branch" not in captured.get("metadata", {})


def test_on_pre_compact_store_memory_uses_app_id():
    """on_pre_compact.store_memory sends app_id top-level."""
    from on_pre_compact import store_memory

    captured = {}

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        captured.update(body)
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        result = store_memory(
            api_key="test-key",
            content="session state content",
            user_id="testuser",
            source="pre-compaction",
            session_id="sess-123",
            project_id="my-project",
            branch="feat/auth",
        )

    assert result is True
    assert captured["app_id"] == "my-project"
    assert captured["user_id"] == "testuser"
    assert "project_id" not in captured.get("metadata", {})
    assert captured["metadata"]["type"] == "session_state"
    assert captured["metadata"]["source"] == "pre-compaction"
    assert captured["metadata"]["branch"] == "feat/auth"
    assert "expiration_date" in captured


def test_capture_compact_summary_store_uses_app_id():
    """capture_compact_summary.store_summary sends app_id top-level."""
    from capture_compact_summary import store_summary

    captured = {}

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        captured.update(body)
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        result = store_summary(
            api_key="test-key",
            summary="compact summary text",
            user_id="testuser",
            session_id="sess-456",
            project_id="my-project",
            branch="main",
        )

    assert result is True
    assert captured["app_id"] == "my-project"
    assert captured["user_id"] == "testuser"
    assert "project_id" not in captured.get("metadata", {})
    assert captured["metadata"]["type"] == "compact_summary"
    assert captured["metadata"]["branch"] == "main"
    assert captured["infer"] is False
    assert "expiration_date" in captured


def test_no_metadata_project_id_anywhere():
    """Ensure none of the write functions put project_id in metadata."""
    from auto_import import post_memory
    from capture_compact_summary import store_summary
    from on_pre_compact import store_memory

    bodies = []

    def mock_urlopen(req, timeout=None):
        body = json.loads(req.data.decode("utf-8"))
        bodies.append(body)
        resp = MagicMock()
        resp.status = 200
        resp.__enter__ = lambda s: s
        resp.__exit__ = MagicMock(return_value=False)
        return resp

    with patch("urllib.request.urlopen", side_effect=mock_urlopen):
        post_memory("k", "c", "u", "f", "proj", "br")
        store_memory("k", "c", "u", "src", "sid", "proj", "br")
        store_summary("k", "s", "u", "sid", "proj", "br")

    for i, body in enumerate(bodies):
        metadata = body.get("metadata", {})
        assert "project_id" not in metadata, f"Write function #{i} still has metadata.project_id"
        assert body.get("app_id") == "proj", f"Write function #{i} missing app_id top-level"
