"""Parity tests for `mem0 init --agent` (Agent Mode bootstrap).

Mirror of ``cli/node/tests/agent-mode.test.ts`` — both files MUST stay in
sync so that the Python and Node CLIs expose an identical surface for the
Agent Mode entrypoint. If you add a flag here, add the same assertion on
the Node side (and vice versa).

Network-bound bootstrap is covered by the platform-side E2E suite
(``backend/tests/e2e/test_05_agent_mode.py``); these tests only verify
the CLI surface that ships in the binary.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys

import pytest

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[mKJHABCDfsu]")


def _strip_ansi(text: str) -> str:
    return _ANSI_RE.sub("", text)


def _run(args: list[str], home_dir: str | None = None) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    for key in list(env.keys()):
        if key.startswith("MEM0_"):
            del env[key]
    env.pop("FORCE_COLOR", None)
    if home_dir:
        env["HOME"] = home_dir
    result = subprocess.run(
        [sys.executable, "-m", "mem0_cli", *args],
        capture_output=True,
        text=True,
        env=env,
        timeout=15,
    )
    return subprocess.CompletedProcess(
        args=result.args,
        returncode=result.returncode,
        stdout=_strip_ansi(result.stdout),
        stderr=_strip_ansi(result.stderr),
    )


@pytest.fixture
def clean_home(tmp_path):
    return str(tmp_path)


class TestInitFlagSurface:
    """`mem0 init --help` must expose the Agent Mode flags."""

    def test_init_help_lists_agent_flag(self):
        result = _run(["init", "--help"])
        assert result.returncode == 0
        assert "--agent" in result.stdout

    def test_init_help_describes_agent_mode(self):
        result = _run(["init", "--help"])
        assert result.returncode == 0
        # Description must mention what --agent actually does so an agent
        # reading the help can self-discover the bootstrap entrypoint.
        assert "Agent Mode" in result.stdout or "unattended" in result.stdout.lower()

    def test_init_help_lists_source_flag(self):
        result = _run(["init", "--help"])
        assert result.returncode == 0
        assert "--source" in result.stdout

    def test_init_help_lists_email_and_code(self):
        # Claim flow flags must remain present alongside Agent Mode flags.
        result = _run(["init", "--help"])
        assert result.returncode == 0
        assert "--email" in result.stdout
        assert "--code" in result.stdout


class TestArgvPreprocessing:
    """`--agent` on `init` must reach init_cmd, not be eaten by the global preprocessor.

    Regression for the bug where the top-level `--agent` JSON-alias was
    stripped from ``sys.argv`` before Typer could bind it to the init
    subcommand, making ``mem0 init --agent`` indistinguishable from a
    plain ``mem0 init`` (interactive wizard).
    """

    def test_init_with_agent_reaches_subcommand(self, clean_home):
        # We can't hit a real backend in unit tests, so we point the CLI at
        # a guaranteed-dead URL and assert the failure is the bootstrap
        # request failing — proving the --agent flag was honored and the
        # bootstrap branch ran, not the interactive wizard.
        result = subprocess.run(
            [sys.executable, "-m", "mem0_cli", "init", "--agent"],
            capture_output=True,
            text=True,
            env={
                **{k: v for k, v in os.environ.items() if not k.startswith("MEM0_")},
                "HOME": clean_home,
                "MEM0_BASE_URL": "http://127.0.0.1:1",  # blackhole
                "FORCE_COLOR": "0",
            },
            timeout=15,
        )
        combined = _strip_ansi(result.stdout + result.stderr).lower()
        # Either we got a connection/network error from the bootstrap POST,
        # or the CLI surfaced an Agent Mode-specific failure message.
        assert (
            "agent" in combined
            or "connect" in combined
            or "network" in combined
            or "fetch" in combined
            or "bootstrap" in combined
        ), f"Expected bootstrap attempt, got: {combined!r}"


class TestJsonEnvelopeParity:
    """`mem0 init --agent --json` should produce a JSON envelope on success.

    Without a live backend we can only assert the failure shape: when the
    backend is unreachable, the CLI must still exit non-zero AND not crash
    on a Python traceback (which would mean we leaked an exception past
    the agent-mode handler).
    """

    def test_init_agent_json_no_traceback_on_network_failure(self, clean_home):
        result = subprocess.run(
            [sys.executable, "-m", "mem0_cli", "init", "--agent", "--json"],
            capture_output=True,
            text=True,
            env={
                **{k: v for k, v in os.environ.items() if not k.startswith("MEM0_")},
                "HOME": clean_home,
                "MEM0_BASE_URL": "http://127.0.0.1:1",
                "FORCE_COLOR": "0",
            },
            timeout=15,
        )
        combined = _strip_ansi(result.stdout + result.stderr)
        assert "Traceback (most recent call last)" not in combined
        assert result.returncode != 0


class TestInitInCommandList:
    """`mem0 --help` must list `init` so agents walking the top-level help
    can discover the Agent Mode entrypoint without prior knowledge."""

    def test_top_level_help_lists_init(self):
        result = _run(["--help"])
        assert result.returncode == 0
        assert "init" in result.stdout
