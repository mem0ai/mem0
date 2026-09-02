from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = HOST.parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from scripts.build import build  # noqa: E402

SPEC = importlib.util.spec_from_file_location("kimi_adapter", HOST / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_normalizes_kimi_payload() -> None:
    value = adapter.normalize(
        {"agent_name": "sidekick", "tool_output": "done", "response": "finished"}
    )

    assert value["agent_type"] == "sidekick"
    assert value["agent_id"] == "sidekick"
    assert value["tool_response"] == "done"
    assert value["last_assistant_message"] == "finished"


def test_native_kimi_bundle_uses_inline_native_contract(tmp_path: Path) -> None:
    root = build("kimi", "native", tmp_path / "kimi")

    manifest = json.loads((root / "kimi.plugin.json").read_text(encoding="utf-8"))
    assert manifest["skills"] == "./skills/"
    assert manifest["agents"] == "./agents/"
    assert manifest["mcpServers"]["mem0"]["args"] == ["./core/mcp_server.py"]
    assert {hook["event"] for hook in manifest["hooks"]} >= {
        "SessionStart",
        "UserPromptSubmit",
        "PostToolUse",
        "SubagentStart",
        "SubagentStop",
        "PreCompact",
        "SessionEnd",
    }
    assert (root / "agents" / "sidekick.md").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))
