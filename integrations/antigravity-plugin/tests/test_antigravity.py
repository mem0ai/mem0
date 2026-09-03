from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))

from build.build import build  # noqa: E402

SPEC = importlib.util.spec_from_file_location("antigravity_adapter", HOST / "hooks" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_normalizes_antigravity_camel_case_payload() -> None:
    value = adapter.normalize(
        {
            "conversationId": "conversation-1",
            "workspacePaths": ["/repo"],
            "transcriptPath": "/transcript.jsonl",
            "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
            "error": "failed",
        }
    )

    assert value["session_id"] == "conversation-1"
    assert value["cwd"] == "/repo"
    assert value["transcript_path"] == "/transcript.jsonl"
    assert value["tool_name"] == "run_command"
    assert value["tool_input"] == {"CommandLine": "pytest"}
    assert value["tool_response"] == "failed"


def test_native_antigravity_bundle_uses_supported_events(tmp_path: Path) -> None:
    root = build("antigravity", "native", tmp_path / "antigravity")

    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    hooks = json.loads((root / "hooks.json").read_text(encoding="utf-8"))["mem0"]
    assert manifest["$schema"] == "https://antigravity.google/schemas/v1/plugin.json"
    assert set(hooks) == {"PreInvocation", "PostToolUse", "Stop"}
    assert (root / "mcp_config.json").is_file()
    assert (root / "agents" / "sidekick" / "agent.md").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))
