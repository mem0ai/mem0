"""Tests for parse_mem0_config.py — mem0.md retention policy parser."""

from __future__ import annotations

import json
import os
import subprocess
import sys

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


# ---------------------------------------------------------------------------
# parse_retention — unit tests
# ---------------------------------------------------------------------------


def test_parse_retention_valid_section():
    """parse_retention extracts day-count policies correctly."""
    from parse_mem0_config import parse_retention

    content = """\
# Project Config

## Retention

session_state: 90d
compact_summary: 60d
decision: 180d
"""
    result = parse_retention(content)
    assert result == {
        "session_state": 90,
        "compact_summary": 60,
        "decision": 180,
    }


def test_parse_retention_forever_returns_none():
    """parse_retention maps 'forever' to None."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

user_preference: forever
anti_pattern: forever
session_state: 30d
"""
    result = parse_retention(content)
    assert result["user_preference"] is None
    assert result["anti_pattern"] is None
    assert result["session_state"] == 30


def test_parse_retention_no_section_returns_empty():
    """parse_retention returns {} when there is no ## Retention heading."""
    from parse_mem0_config import parse_retention

    content = """\
# Project Config

## Some Other Section

key: value
"""
    result = parse_retention(content)
    assert result == {}


def test_parse_retention_stops_at_next_heading():
    """parse_retention stops reading at the next ## heading."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 7d

## Other Section

other_key: 999d
"""
    result = parse_retention(content)
    assert "session_state" in result
    assert "other_key" not in result


def test_parse_retention_malformed_lines_skipped():
    """Malformed lines (no colon, bad day format) are silently ignored."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 90d
bad_line_no_colon
another: badvalue
decision: 30d
"""
    result = parse_retention(content)
    assert result == {"session_state": 90, "decision": 30}


def test_parse_retention_comments_ignored():
    """Inline # comments are stripped before parsing."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

session_state: 90d  # rolling 90-day window
user_preference: forever  # never prune preferences
"""
    result = parse_retention(content)
    assert result["session_state"] == 90
    assert result["user_preference"] is None


def test_parse_retention_case_insensitive_heading():
    """## retention (lowercase) is matched the same as ## Retention."""
    from parse_mem0_config import parse_retention

    content = """\
## retention

session_state: 14d
"""
    result = parse_retention(content)
    assert result == {"session_state": 14}


def test_parse_retention_empty_section_returns_empty():
    """A ## Retention section with no valid lines returns {}."""
    from parse_mem0_config import parse_retention

    content = """\
## Retention

# only comments here

## Next Section
"""
    result = parse_retention(content)
    assert result == {}


# ---------------------------------------------------------------------------
# load_retention_policies — integration tests with tmp files
# ---------------------------------------------------------------------------


def test_load_retention_policies_with_tmp_file(tmp_path):
    """load_retention_policies reads a real mem0.md from disk."""
    from parse_mem0_config import load_retention_policies

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        """\
# My Project

## Retention

session_state: 90d
compact_summary: 60d
decision: forever
""",
        encoding="utf-8",
    )

    result = load_retention_policies(str(tmp_path))
    assert result == {
        "session_state": 90,
        "compact_summary": 60,
        "decision": None,
    }


def test_load_retention_policies_no_mem0_md_returns_empty(tmp_path):
    """load_retention_policies returns {} when no mem0.md exists."""
    from parse_mem0_config import load_retention_policies

    result = load_retention_policies(str(tmp_path))
    assert result == {}


def test_load_retention_policies_no_retention_section_returns_empty(tmp_path):
    """load_retention_policies returns {} when mem0.md has no ## Retention."""
    from parse_mem0_config import load_retention_policies

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        """\
# My Project

Some general project notes here.
No retention section.
""",
        encoding="utf-8",
    )

    result = load_retention_policies(str(tmp_path))
    assert result == {}


def test_load_retention_policies_defaults_to_cwd(tmp_path, monkeypatch):
    """load_retention_policies uses os.getcwd() when cwd is None."""
    from parse_mem0_config import load_retention_policies

    monkeypatch.chdir(tmp_path)
    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text("## Retention\nsession_state: 45d\n", encoding="utf-8")

    result = load_retention_policies()  # no cwd arg
    assert result == {"session_state": 45}


# ---------------------------------------------------------------------------
# CLI / main() — subprocess test
# ---------------------------------------------------------------------------


def test_cli_main_prints_json(tmp_path):
    """CLI: python parse_mem0_config.py <cwd> prints valid JSON."""
    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        "## Retention\nsession_state: 90d\nuser_preference: forever\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_mem0_config.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["session_state"] == 90
    assert data["user_preference"] is None


def test_cli_main_no_file_prints_empty_json(tmp_path):
    """CLI: prints '{}' when no mem0.md exists."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_mem0_config.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert json.loads(result.stdout) == {}


# ---------------------------------------------------------------------------
# parse_section_kv — unit tests
# ---------------------------------------------------------------------------


def test_parse_section_kv_basic():
    """parse_section_kv extracts key-value pairs from a named section."""
    from parse_mem0_config import parse_section_kv

    content = """\
## Search

default_limit: 10
boost_recency: true
"""
    result = parse_section_kv(content, "Search")
    assert result == {"default_limit": "10", "boost_recency": "true"}


def test_parse_section_kv_missing_section():
    """parse_section_kv returns {} when section doesn't exist."""
    from parse_mem0_config import parse_section_kv

    result = parse_section_kv("## Other\nfoo: bar\n", "Search")
    assert result == {}


def test_parse_section_kv_stops_at_next_heading():
    """parse_section_kv stops at the next ## heading."""
    from parse_mem0_config import parse_section_kv

    content = """\
## Identity

user_id: kartik
project_id: mem0

## Other

ignored: yes
"""
    result = parse_section_kv(content, "Identity")
    assert result == {"user_id": "kartik", "project_id": "mem0"}
    assert "ignored" not in result


# ---------------------------------------------------------------------------
# parse_section_list — unit tests
# ---------------------------------------------------------------------------


def test_parse_section_list_basic():
    """parse_section_list extracts list items from a named section."""
    from parse_mem0_config import parse_section_list

    content = """\
## Categories

- architecture_decisions
- bug_fixes
- coding_conventions
"""
    result = parse_section_list(content, "Categories")
    assert result == ["architecture_decisions", "bug_fixes", "coding_conventions"]


def test_parse_section_list_bare_lines():
    """parse_section_list works with bare lines (no bullet prefix)."""
    from parse_mem0_config import parse_section_list

    content = """\
## Categories

architecture_decisions
bug_fixes
"""
    result = parse_section_list(content, "Categories")
    assert result == ["architecture_decisions", "bug_fixes"]


def test_parse_section_list_missing_section():
    """parse_section_list returns [] when section doesn't exist."""
    from parse_mem0_config import parse_section_list

    result = parse_section_list("## Other\n- foo\n", "Categories")
    assert result == []


# ---------------------------------------------------------------------------
# load_full_config — integration tests
# ---------------------------------------------------------------------------


def test_load_full_config_all_sections(tmp_path):
    """load_full_config extracts all sections from mem0.md."""
    from parse_mem0_config import load_full_config

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        """\
# My Project

## Retention

session_state: 90d
decision: forever

## Search

default_limit: 20
boost_recency: true

## Categories

- architecture_decisions
- bug_fixes
- security_constraints

## Identity

user_id: kartik
project_id: my-project
""",
        encoding="utf-8",
    )

    config = load_full_config(str(tmp_path))
    assert config["retention"] == {"session_state": 90, "decision": None}
    assert config["search"] == {"default_limit": "20", "boost_recency": "true"}
    assert config["categories"] == ["architecture_decisions", "bug_fixes", "security_constraints"]
    assert config["identity"] == {"user_id": "kartik", "project_id": "my-project"}


def test_load_full_config_partial_sections(tmp_path):
    """load_full_config only includes sections that exist."""
    from parse_mem0_config import load_full_config

    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text("## Retention\nsession_state: 30d\n", encoding="utf-8")

    config = load_full_config(str(tmp_path))
    assert "retention" in config
    assert "search" not in config
    assert "categories" not in config
    assert "identity" not in config


def test_load_full_config_no_file(tmp_path):
    """load_full_config returns {} when no mem0.md exists."""
    from parse_mem0_config import load_full_config

    config = load_full_config(str(tmp_path))
    assert config == {}


def test_cli_full_flag(tmp_path):
    """CLI: --full prints all sections as JSON."""
    mem0_md = tmp_path / "mem0.md"
    mem0_md.write_text(
        "## Retention\nsession_state: 90d\n\n## Search\nlimit: 10\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, "parse_mem0_config.py"), "--full", str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert "retention" in data
    assert "search" in data
