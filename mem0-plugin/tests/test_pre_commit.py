"""Tests for on_pre_commit.py — pre-commit memory capture."""

from __future__ import annotations

import os
from unittest.mock import MagicMock

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


def test_import_succeeds():
    """on_pre_commit module can be imported."""
    import on_pre_commit

    assert hasattr(on_pre_commit, "main")


def test_no_api_key_exits_zero(monkeypatch):
    """main() exits 0 when no API key is set."""
    import on_pre_commit

    monkeypatch.delenv("MEM0_API_KEY", raising=False)
    monkeypatch.delenv("CLAUDE_PLUGIN_OPTION_MEM0_API_KEY", raising=False)
    monkeypatch.setattr("sys.stdin", MagicMock(isatty=lambda: True))

    assert on_pre_commit.main() == 0


def test_empty_diff_exits_zero(monkeypatch):
    """main() exits 0 when stdin diff is empty."""
    from io import StringIO

    import on_pre_commit

    monkeypatch.setenv("MEM0_API_KEY", "test-key")
    monkeypatch.setattr("sys.stdin", StringIO(""))

    assert on_pre_commit.main() == 0


def test_get_staged_summary_runs():
    """get_staged_summary doesn't crash even outside a git repo."""
    import on_pre_commit

    result = on_pre_commit.get_staged_summary()
    assert isinstance(result, str)


def test_get_commit_message_runs():
    """get_commit_message doesn't crash even outside a git repo."""
    import on_pre_commit

    result = on_pre_commit.get_commit_message()
    assert isinstance(result, str)
