"""Integration tests — invoke CLI as subprocess to test end-to-end.

These tests launch the CLI as a real subprocess, so they must manage
environment isolation themselves (monkeypatch doesn't cross process
boundaries).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mKJHABCDfsu]")


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes so substring checks work regardless of color mode."""
    return _ANSI_RE.sub("", text)


def _run(
    args: list[str],
    env_override: dict | None = None,
    home_dir: str | None = None,
) -> subprocess.CompletedProcess:
    """Run mem0 CLI command and capture output.

    Args:
        args: CLI arguments.
        env_override: Extra env vars to set.
        home_dir: If provided, set HOME to this path so the subprocess
            reads config from ``<home_dir>/.mem0/config.json`` instead
            of the user's real config.  This is critical for tests that
            depend on a clean (no API key) or custom config state.

    Returns a CompletedProcess whose stdout/stderr have ANSI escape codes
    stripped.  GitHub Actions sets FORCE_COLOR=1 which causes Rich/Typer to
    fragment option names like --user-id into separately-styled ANSI segments,
    making plain ``in`` checks fail.  Stripping here is version-agnostic and
    ensures all assertions see the same plain text regardless of terminal env.
    """
    env = os.environ.copy()
    # Strip all MEM0_ env vars so tests start clean
    for key in list(env.keys()):
        if key.startswith("MEM0_"):
            del env[key]
    env.pop("FORCE_COLOR", None)
    if home_dir:
        env["HOME"] = home_dir
    if env_override:
        env.update(env_override)
    result = subprocess.run(
        [sys.executable, "-m", "mem0_cli", *args],
        capture_output=True,
        text=True,
        env=env,
    )
    return subprocess.CompletedProcess(
        args=result.args,
        returncode=result.returncode,
        stdout=_strip_ansi(result.stdout),
        stderr=_strip_ansi(result.stderr),
    )


@pytest.fixture
def clean_home(tmp_path):
    """Return a temp directory to use as HOME, ensuring no ~/.mem0 exists."""
    return str(tmp_path)


class TestCLIIntegration:
    """Tests that only inspect help text / version — no config needed."""

    def test_help(self):
        result = _run(["--help"])
        assert result.returncode == 0
        assert "mem0" in result.stdout
        assert "add" in result.stdout
        assert "search" in result.stdout

    def test_add_help(self):
        result = _run(["add", "--help"])
        assert result.returncode == 0
        assert "user-id" in result.stdout
        assert "messages" in result.stdout

    def test_add_help_has_scope_panel(self):
        """Verify rich_help_panel grouping shows in help output."""
        result = _run(["add", "--help"])
        assert result.returncode == 0
        assert "Scope" in result.stdout

    def test_search_help(self):
        result = _run(["search", "--help"])
        assert result.returncode == 0
        assert "top-k" in result.stdout

    def test_list_help(self):
        result = _run(["list", "--help"])
        assert result.returncode == 0
        assert "page-size" in result.stdout

    def test_delete_help(self):
        result = _run(["delete", "--help"])
        assert result.returncode == 0
        assert "--all" in result.stdout
        assert "--entity" in result.stdout
        assert "--project" in result.stdout
        assert "--force" in result.stdout
        assert "--dry-run" in result.stdout

    def test_entity_list_help(self):
        result = _run(["entity", "list", "--help"])
        assert result.returncode == 0
        assert "entity-type" in result.stdout.lower() or "entity_type" in result.stdout.lower()

    def test_entity_delete_help(self):
        result = _run(["entity", "delete", "--help"])
        assert result.returncode == 0
        assert "--user-id" in result.stdout
        assert "--force" in result.stdout

    def test_import_help(self):
        result = _run(["import", "--help"])
        assert result.returncode == 0

    def test_no_args_shows_help(self):
        """no_args_is_help=True makes Typer print help and exit with code 2."""
        result = _run([])
        # Typer returns exit code 2 for "no command given" — this is standard
        # Click/Typer behaviour and not an error.
        assert result.returncode in (0, 2)
        assert "Usage" in result.stdout


class TestCLIIsolated:
    """Tests that need a clean HOME to avoid reading the user's real config."""

    def test_add_no_key_errors(self, clean_home):
        """Without an API key, `mem0 add` must fail with a helpful message."""
        result = _run(
            ["add", "test", "--user-id", "alice"],
            home_dir=clean_home,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "API key" in combined or "api" in combined.lower() or "Error" in combined

    def test_search_no_key_errors(self, clean_home):
        """Without an API key, `mem0 search` must fail."""
        result = _run(
            ["search", "preferences", "--user-id", "alice"],
            home_dir=clean_home,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "API key" in combined or "Error" in combined

    def test_list_no_key_errors(self, clean_home):
        """Without an API key, `mem0 list` must fail."""
        result = _run(["list"], home_dir=clean_home)
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "API key" in combined or "Error" in combined

    def test_delete_no_id_no_all_errors(self, clean_home):
        """Delete without memory_id, --all, or --entity must fail."""
        result = _run(
            ["delete", "--api-key", "m0-fake-key"],
            home_dir=clean_home,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert (
            "memory ID" in combined.lower()
            or "--all" in combined
            or "--entity" in combined
            or "Error" in combined
        )

    def test_config_show_clean(self, clean_home):
        """config show with no config should still work."""
        result = _run(["config", "show"], home_dir=clean_home)
        assert result.returncode == 0
        assert "backend" in result.stdout.lower() or "platform" in result.stdout.lower()

    def test_config_set_and_get_roundtrip(self, clean_home):
        """config set then config get should return the set value."""
        _run(
            ["config", "set", "defaults.user_id", "integration-test-user"],
            home_dir=clean_home,
        )
        result = _run(
            ["config", "get", "defaults.user_id"],
            home_dir=clean_home,
        )
        assert result.returncode == 0
        assert "integration-test-user" in result.stdout

    def test_import_nonexistent_file(self, clean_home):
        """Importing a nonexistent file should fail gracefully."""
        result = _run(
            ["import", "/nonexistent/file.json", "--api-key", "m0-fake"],
            home_dir=clean_home,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "Failed" in combined or "Error" in combined or "error" in combined

    def test_add_no_content_errors(self, clean_home):
        """add with no text/messages/file should fail."""
        result = _run(
            ["add", "--user-id", "alice", "--api-key", "m0-fake"],
            home_dir=clean_home,
        )
        assert result.returncode != 0
        combined = result.stderr + result.stdout
        assert "No content" in combined or "Error" in combined


class TestCLINewFeatures:
    """Tests for MCP parity features: --limit, entities delete."""

    def test_search_help_has_limit(self):
        result = _run(["search", "--help"])
        assert result.returncode == 0
        assert "--limit" in result.stdout

    def test_delete_entity_via_delete_flag(self):
        """delete --entity should appear in help output."""
        result = _run(["delete", "--help"])
        assert result.returncode == 0
        assert "--entity" in result.stdout

    def test_entity_delete_has_scope_options(self):
        """entity delete should expose scope options."""
        result = _run(["entity", "delete", "--help"])
        assert result.returncode == 0
        assert "--user-id" in result.stdout
        assert "--force" in result.stdout
        assert "--app-id" in result.stdout
        assert "--run-id" in result.stdout
