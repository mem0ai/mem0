from __future__ import annotations

import json
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))

from build.build import build  # noqa: E402


def test_codex_hooks_use_native_events_and_plugin_paths() -> None:
    hooks = json.loads((HOST / "hooks" / "hooks.json").read_text(encoding="utf-8"))["hooks"]

    assert set(hooks) == {
        "SessionStart",
        "UserPromptSubmit",
        "PostToolUse",
        "Stop",
        "PreCompact",
        "SessionEnd",
    }
    commands = [hook["command"] for groups in hooks.values() for group in groups for hook in group["hooks"]]
    assert all("${PLUGIN_ROOT}/hooks/adapter.py" in command for command in commands)
    assert any("flush --reason pre-compact" in command for command in commands)
    assert any("flush --reason session-end" in command for command in commands)


def test_native_codex_bundle_is_self_contained(tmp_path: Path) -> None:
    root = build("codex", "native", tmp_path / "codex")

    manifest = json.loads((root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert manifest["skills"] == "./skills/"
    assert (root / "hooks" / "adapter.py").is_file()
    assert (root / "core" / "mcp_server.py").is_file()
    assert not (root / "agents").exists()
    assert not any(path.is_symlink() for path in root.rglob("*"))
