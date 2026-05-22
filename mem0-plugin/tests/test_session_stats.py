"""Tests for session_stats.py — session-level memory operation tracker."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


@pytest.fixture(autouse=True)
def _isolate_stats_file(tmp_path, monkeypatch):
    """Point STATS_FILE to a temp location so tests don't interfere."""
    stats_file = str(tmp_path / "test_stats.json")
    monkeypatch.setattr("session_stats.STATS_FILE", stats_file)
    yield stats_file


def test_init_creates_file(_isolate_stats_file):
    import session_stats

    session_stats.init()
    assert os.path.isfile(_isolate_stats_file)
    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["adds"] == 0
    assert data["searches"] == 0
    assert data["categories"] == []


def test_record_add_increments(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_add("bug_fixes")
    session_stats.record_add("bug_fixes")
    session_stats.record_add("decisions")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["adds"] == 3
    assert set(data["categories"]) == {"bug_fixes", "decisions"}


def test_record_search_increments(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_search()
    session_stats.record_search()

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["searches"] == 2


def test_report_returns_summary(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_add("architecture_decisions")
    session_stats.record_add("task_learnings")
    session_stats.record_search()
    session_stats.record_search()
    session_stats.record_search()

    result = session_stats.report()
    assert "wrote 2 memories" in result
    assert "retrieved 3" in result
    assert "architecture_decisions" in result
    assert "task_learnings" in result


def test_report_empty_session(_isolate_stats_file):
    import session_stats

    session_stats.init()
    result = session_stats.report()
    assert result == ""


def test_report_cleans_up_file(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_add()
    session_stats.report()
    assert not os.path.isfile(_isolate_stats_file)


def test_record_add_no_category(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_add("")
    session_stats.record_add()

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["adds"] == 2
    assert data["categories"] == []


def test_duplicate_categories_not_added(_isolate_stats_file):
    import session_stats

    session_stats.init()
    session_stats.record_add("bug_fixes")
    session_stats.record_add("bug_fixes")
    session_stats.record_add("bug_fixes")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["adds"] == 3
    assert data["categories"] == ["bug_fixes"]


def test_cli_init(tmp_path):
    """Test CLI invocation: session_stats.py init."""
    env = {**os.environ, "USER": "test"}
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "session_stats.py"), "init"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0


def test_cli_report_no_data(tmp_path):
    """Test CLI invocation: report with no prior init prints fallback."""
    env = {**os.environ, "USER": f"test_{os.getpid()}"}
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "session_stats.py"), "report"],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0
