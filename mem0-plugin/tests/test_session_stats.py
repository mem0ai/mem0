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


def test_peek_returns_json_without_clearing(_isolate_stats_file):
    """peek returns JSON stats without deleting the stats file."""
    import session_stats

    session_stats.init()
    session_stats.record_add("decisions")
    session_stats.record_add("decisions")
    session_stats.record_search()

    result = session_stats.peek()
    data = json.loads(result)
    assert data["adds"] == 2
    assert data["searches"] == 1

    assert os.path.isfile(_isolate_stats_file)


def test_category_counts_tracked(_isolate_stats_file):
    """category_counts tracks per-category add counts."""
    import session_stats

    session_stats.init()
    session_stats.record_add("bug_fixes")
    session_stats.record_add("bug_fixes")
    session_stats.record_add("bug_fixes")
    session_stats.record_add("decisions")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["category_counts"]["bug_fixes"] == 3
    assert data["category_counts"]["decisions"] == 1


def test_category_counts_empty_category_not_tracked(_isolate_stats_file):
    """Empty category string doesn't appear in category_counts."""
    import session_stats

    session_stats.init()
    session_stats.record_add("")
    session_stats.record_add()

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["category_counts"] == {}


def test_recent_ids_tracked(_isolate_stats_file):
    """record_add with memory_id stores ID in recent_ids."""
    import session_stats

    session_stats.init()
    session_stats.record_add("decision", "abc-123")
    session_stats.record_add("convention", "def-456")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert len(data["recent_ids"]) == 2
    assert data["recent_ids"][0]["id"] == "abc-123"
    assert data["recent_ids"][1]["id"] == "def-456"
    assert data["recent_ids"][0]["category"] == "decision"


def test_recent_ids_capped(_isolate_stats_file):
    """recent_ids list is capped at MAX_RECENT_IDS."""
    import session_stats

    session_stats.init()
    for i in range(60):
        session_stats.record_add("test", f"id-{i}")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert len(data["recent_ids"]) == session_stats.MAX_RECENT_IDS
    assert data["recent_ids"][0]["id"] == f"id-{60 - session_stats.MAX_RECENT_IDS}"


def test_recent_ids_empty_without_memory_id(_isolate_stats_file):
    """record_add without memory_id doesn't add to recent_ids."""
    import session_stats

    session_stats.init()
    session_stats.record_add("decision")
    session_stats.record_add("convention", "")

    with open(_isolate_stats_file) as f:
        data = json.load(f)
    assert data["recent_ids"] == []


def test_cli_peek(tmp_path):
    """Test CLI invocation: session_stats.py peek outputs JSON."""
    env = {**os.environ, "USER": "test"}
    subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "session_stats.py"), "init"],
        capture_output=True, text=True, env=env,
    )
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "session_stats.py"), "peek"],
        capture_output=True, text=True, env=env,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "adds" in data
