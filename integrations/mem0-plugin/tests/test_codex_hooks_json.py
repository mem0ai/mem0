"""Regression test for #6181: Codex lifecycle hooks exited 1 on every event on
native Windows.

`command` used POSIX env-prefix syntax (`VAR=value script.sh`), which only a
POSIX shell can parse. Codex hands that string to the native shell, so cmd tried
to execute `MEM0_PLATFORM=codex` as a program name and failed immediately.

The fix uses Codex's platform-specific `command_windows` field: on Windows Codex
prefers `command_windows` and runs it via cmd, so each platform gets a string
written for the shell that will actually parse it. `command` stays in its
original POSIX form for macOS/Linux; `command_windows` routes through
`bash -c "..."` so cmd only ever sees `bash` plus one quoted argument.

These tests pin both halves: `command` must stay POSIX-native, and
`command_windows` must exist for every hook and must not leak POSIX-only syntax
into cmd.
"""

from __future__ import annotations

import json
import os
import re
import sys

HOOKS_FILE = os.path.join(os.path.dirname(__file__), "..", "hooks", "codex-hooks.json")

# A bare `VAR=value` token at the start of a command string. Fine for the POSIX
# `command`; fatal for `command_windows`, which cmd parses.
BARE_ENV_PREFIX = re.compile(r"^\s*[A-Z_][A-Z0-9_]*=\S")


def _load():
    with open(HOOKS_FILE) as f:
        return json.load(f)


def _iter_hooks(config: dict):
    for event, entries in config.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    yield event, hook


def test_codex_hooks_json_is_valid_json():
    _load()


def test_every_hook_defines_a_windows_command():
    hooks = list(_iter_hooks(_load()))
    assert hooks, "expected at least one hook command in codex-hooks.json"

    for event, hook in hooks:
        assert hook.get("command_windows"), (
            f"{event} hook has no `command_windows`. Without it Codex falls back "
            f"to `command`, whose POSIX env-prefix syntax cmd cannot parse (#6181)."
        )


def test_windows_commands_route_through_an_explicit_interpreter():
    for event, hook in _iter_hooks(_load()):
        command_windows = hook["command_windows"]

        assert not BARE_ENV_PREFIX.match(command_windows), (
            f"{event} `command_windows` starts with a bare `VAR=value` prefix, "
            f"which cmd cannot parse: {command_windows!r}"
        )
        assert command_windows.startswith("bash "), (
            f"{event} `command_windows` must invoke bash explicitly so cmd only "
            f"sees `bash` plus a quoted argument: {command_windows!r}"
        )


def test_posix_commands_invoke_the_script_directly():
    """The Unix path must not pay for the Windows workaround: no `bash -c`
    wrapper, no nested quoting, and no dependency on bash being installed under
    that name."""
    for event, hook in _iter_hooks(_load()):
        command = hook["command"]

        assert command.startswith("MEM0_PLATFORM=codex "), (
            f"{event} `command` should keep the plain POSIX form so macOS/Linux "
            f"behaviour is unchanged: {command!r}"
        )
        assert "bash -c" not in command, (
            f"{event} `command` should not wrap the script in `bash -c` — that is "
            f"what `command_windows` is for: {command!r}"
        )


def test_both_variants_run_the_same_script():
    for event, hook in _iter_hooks(_load()):
        script = hook["command"].split()[-1]
        assert script in hook["command_windows"], (
            f"{event} `command` and `command_windows` disagree on which script to "
            f"run: {script!r} vs {hook['command_windows']!r}"
        )


def test_installer_template_substitution_survives_a_windows_plugin_root(monkeypatch):
    """install_codex_hooks.load_template() substitutes ${PLUGIN_ROOT} into the raw
    JSON text. A Windows path splices in bare backslashes, so
    ``C:\\Users\\...`` made json.loads fail with "Invalid \\escape". The old hard
    Windows block in the installer hid that; now that Windows can reach this code
    path, the escaping has to hold."""
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
    import install_codex_hooks

    windows_root = r"C:\Users\dev\.codex\plugins\mem0-plugin"
    monkeypatch.setattr(install_codex_hooks, "PLUGIN_ROOT", windows_root)

    config = install_codex_hooks.load_template()  # must not raise

    for _, hook in _iter_hooks(config):
        assert "${PLUGIN_ROOT}" not in hook["command_windows"]
        assert windows_root in hook["command_windows"]
