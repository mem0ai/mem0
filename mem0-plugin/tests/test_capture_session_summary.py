"""Tests for capture_session_summary.py."""

from __future__ import annotations

import io
import json
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, os.path.abspath(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def _clean_module():
    yield
    sys.modules.pop("capture_session_summary", None)


def test_auto_save_false_skips_capture(monkeypatch):
    import capture_session_summary

    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    monkeypatch.setattr(capture_session_summary, "resolve_config", lambda: {"auto_save": False})

    stored = []
    monkeypatch.setattr(capture_session_summary, "store_summary", lambda *a, **kw: stored.append(a))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"transcript_path": "/fake", "session_id": "s1"})))

    capture_session_summary.main()

    assert stored == [], "store_summary must not be called when auto_save is false"


def test_auto_save_true_proceeds(monkeypatch, tmp_path):
    import capture_session_summary

    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "message": {"content": "x" * 200}}) + "\n"
    )

    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    monkeypatch.setattr(capture_session_summary, "resolve_config", lambda: {"auto_save": True})

    stored = []
    monkeypatch.setattr(capture_session_summary, "store_summary", lambda *a, **kw: stored.append(a))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"transcript_path": str(transcript), "session_id": "s1"})))

    capture_session_summary.main()

    assert stored, "store_summary should be called when auto_save is true"


def test_auto_save_default_proceeds(monkeypatch, tmp_path):
    import capture_session_summary

    transcript = tmp_path / "t.jsonl"
    transcript.write_text(
        json.dumps({"type": "assistant", "message": {"content": "x" * 200}}) + "\n"
    )

    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    monkeypatch.setattr(capture_session_summary, "resolve_config", lambda: {})

    stored = []
    monkeypatch.setattr(capture_session_summary, "store_summary", lambda *a, **kw: stored.append(a))
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"transcript_path": str(transcript), "session_id": "s1"})))

    capture_session_summary.main()

    assert stored, "store_summary should be called when auto_save is absent from config (default true)"
