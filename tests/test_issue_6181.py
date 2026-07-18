"""Regression test for Issue #6181.

Codex lifecycle hook commands are executed by the native shell on Windows.
The hook template must therefore avoid POSIX-only env-prefix commands and
must not rely on .sh files being directly executable.
"""

import importlib.util
import json
import os
import re
from pathlib import PurePosixPath


def test_issue_6181():
    plugin_root = os.path.join(
        os.path.dirname(__file__),
        "..",
        "integrations",
        "mem0-plugin",
    )
    installer_path = os.path.join(plugin_root, "scripts", "install_codex_hooks.py")
    spec = importlib.util.spec_from_file_location("install_codex_hooks", installer_path)
    installer = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(installer)

    assert installer.OWNER_MARKER == "mem0-plugin"

    hooks_path = os.path.join(plugin_root, "hooks", "codex-hooks.json")
    with open(hooks_path) as f:
        config = json.load(f)

    commands = [
        h["command"] for entries in config["hooks"].values() for entry in entries for h in entry.get("hooks", [])
    ]
    assert commands, "expected at least one codex hook command"

    env_prefix = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
    for cmd in commands:
        assert not env_prefix.match(cmd), f"Windows native shells cannot parse POSIX env-prefix hook command: {cmd}"

        command_parts = cmd.split()
        script_invocations = [
            (index, part.strip("\"'"))
            for index, part in enumerate(command_parts)
            if PurePosixPath(part.strip("\"'")).suffix == ".sh"
        ]
        for index, _script in script_invocations:
            launcher = command_parts[index - 1] if index > 0 else ""
            assert PurePosixPath(launcher.strip("\"'")).name in {
                "bash",
                "bash.exe",
            }, f"Windows Codex hooks must launch shell scripts through bash or a cross-platform shim: {cmd}"
