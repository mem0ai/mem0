"""Regression test for #6181: Codex hooks must not rely on POSIX env-prefix
syntax (`VAR=value command`) at the top level of the command string, since
Codex hands that string to the native shell (cmd/PowerShell on Windows),
which cannot parse it and exits 1 on every event.

Commands must instead route through an explicit interpreter (e.g.
`bash -c "..."`) so env-var assignment is parsed by that interpreter, not by
whatever shell the host OS defaults to.
"""

from __future__ import annotations

import json
import os
import re

HOOKS_FILE = os.path.join(
    os.path.dirname(__file__), "..", "hooks", "codex-hooks.json"
)

# A bare `VAR=value` token at the start of the command (or right after a
# shell operator like `&&`/`;`), NOT inside a quoted string passed to an
# interpreter, is the pattern that breaks native Windows shells.
BARE_ENV_PREFIX = re.compile(r"^\s*[A-Z_][A-Z0-9_]*=\S")


def _iter_commands(config: dict):
    for event, entries in config.get("hooks", {}).items():
        for entry in entries:
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command":
                    yield event, hook["command"]


def test_codex_hooks_json_is_valid_json():
    with open(HOOKS_FILE) as f:
        json.load(f)


def test_no_bare_env_prefix_in_commands():
    with open(HOOKS_FILE) as f:
        config = json.load(f)

    commands = list(_iter_commands(config))
    assert commands, "expected at least one hook command in codex-hooks.json"

    for event, command in commands:
        assert not BARE_ENV_PREFIX.match(command), (
            f"{event} hook command starts with a bare `VAR=value` prefix, "
            f"which native Windows shells cannot parse: {command!r}"
        )


def test_commands_route_through_an_explicit_interpreter():
    with open(HOOKS_FILE) as f:
        config = json.load(f)

    for event, command in _iter_commands(config):
        assert command.startswith("bash "), (
            f"{event} hook command should invoke bash explicitly so it runs "
            f"identically under cmd/PowerShell/POSIX shells: {command!r}"
        )
