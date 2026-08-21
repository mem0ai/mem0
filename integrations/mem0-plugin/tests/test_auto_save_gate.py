"""Tests that auto_save=false actually suppresses the session-start auto-import.

auto_import.py writes memories, so it belongs behind the same MEM0_AUTO_SAVE
guard as every other writer in the plugin. It was previously launched
unconditionally, which made `auto_save: false` in ~/.mem0/settings.json a no-op
for that path: every session start still imported CLAUDE.md and friends.

These drive the real hook rather than importing Python, because the bug lives in
the shell wiring and is invisible from the module level.
"""

from __future__ import annotations

import os
import stat
import subprocess

import pytest

SCRIPTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "scripts"))
HOOK = os.path.join(SCRIPTS_DIR, "on_session_start.sh")


def _python_stub(tmp_path, log_path):
    """A python3 that records auto_import.py invocations, then delegates.

    Delegation matters: _identity.sh shells out to python3 to parse
    ~/.mem0/settings.json, so a stub that does not exec the real interpreter
    would break the very setting under test.
    """
    stub_dir = tmp_path / "stub"
    stub_dir.mkdir(parents=True, exist_ok=True)
    stub = stub_dir / "python3"
    stub.write_text(
        "#!/bin/sh\n"
        'for a in "$@"; do\n'
        "  case \"$a\" in\n"
        f'    *auto_import.py) echo ran >> "{log_path}" ;;\n'
        "  esac\n"
        "done\n"
        f'exec "{os.path.realpath(__import__("sys").executable)}" "$@"\n'
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return stub_dir


def _run_hook(tmp_path, home, auto_save):
    """Run the session-start hook with auto_save set, return True if it imported."""
    mem0_dir = home / ".mem0"
    mem0_dir.mkdir(parents=True, exist_ok=True)
    # _identity.sh re-exports MEM0_AUTO_SAVE from this file, so the file is
    # authoritative -- passing the env var alone would not exercise the path.
    (mem0_dir / "settings.json").write_text('{"auto_save": %s}\n' % ("true" if auto_save else "false"))

    log_path = tmp_path / f"import-{auto_save}.log"
    stub_dir = _python_stub(tmp_path / f"case-{auto_save}", log_path)

    env = dict(os.environ)
    env["PATH"] = f"{stub_dir}{os.pathsep}{env['PATH']}"
    env["HOME"] = str(home)
    # A key must be present or the hook exits early with a setup message. It is
    # never used: no CLAUDE.md exists in cwd, so auto_import returns immediately.
    env["MEM0_API_KEY"] = "m0-test-key-not-real"
    env.pop("MEM0_PROJECT_ID", None)

    subprocess.run(
        ["sh", HOOK],
        input='{"session_id":"t","cwd":"%s","source":"startup"}' % tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    # The hook backgrounds auto_import, so give it a moment to land.
    for _ in range(50):
        if log_path.exists() and log_path.stat().st_size:
            return True
        subprocess.run(["sleep", "0.1"], check=False)
    return False


@pytest.mark.parametrize("auto_save,expected", [(True, True), (False, False)])
def test_session_start_import_respects_auto_save(tmp_path, monkeypatch, auto_save, expected):
    """auto-import runs iff auto_save is not false."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    assert _run_hook(tmp_path, home, auto_save) is expected


def test_auto_import_is_guarded_in_the_hook_source():
    """The launch is inside a MEM0_AUTO_SAVE guard, not merely near one.

    on_session_start.sh already contains an unrelated MEM0_AUTO_SAVE check in
    the `compact` branch, so grepping for the variable is not enough -- this
    pins the guard to the auto_import call itself.
    """
    lines = open(HOOK, encoding="utf-8").read().splitlines()
    call = next(i for i, ln in enumerate(lines) if "auto_import.py" in ln)
    preceding = "\n".join(lines[max(0, call - 6) : call])
    assert "MEM0_AUTO_SAVE" in preceding, (
        "auto_import.py is launched without a MEM0_AUTO_SAVE guard above it"
    )
