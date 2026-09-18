from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))

from build.build import build  # noqa: E402

SPEC = importlib.util.spec_from_file_location("copilot_adapter", HOST / "hooks" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_normalizes_copilot_payload() -> None:
    raw_payload = {
        "sessionId": "session-xyz",
        "cwd": "/workspace/project",
        "prompt": "Optimize database queries",
        "toolName": "bash",
        "toolInput": {"command": "npm test"},
        "output": "Tests passed",
        "error": "Syntax error",
        "response": "Here is the optimized query",
    }

    normalized = adapter.normalize(raw_payload)

    assert normalized["session_id"] == "session-xyz"
    assert normalized["cwd"] == "/workspace/project"
    assert normalized["prompt"] == "Optimize database queries"
    assert normalized["tool_name"] == "bash"
    assert normalized["tool_input"] == {"command": "npm test"}
    assert normalized["tool_response"] == "Syntax error"
    assert normalized["last_assistant_message"] == "Here is the optimized query"


def test_copilot_hooks_configuration() -> None:
    hooks_file = HOST / "hooks.json"
    assert hooks_file.is_file()
    data = json.loads(hooks_file.read_text(encoding="utf-8"))
    assert data.get("version") == 1
    hooks = data.get("hooks", {})

    expected_events = {"sessionStart", "userPromptSubmitted", "postToolUse", "agentStop", "sessionEnd"}
    assert set(hooks.keys()) == expected_events

    for event_name, hook_list in hooks.items():
        assert len(hook_list) >= 1
        for hook_entry in hook_list:
            assert hook_entry.get("type") == "command"
            assert "${PLUGIN_ROOT}/hooks/adapter.py" in hook_entry.get("bash", "")
            assert hook_entry.get("timeoutSec", 0) <= 5


def test_copilot_manifest_and_mcp() -> None:
    manifest = json.loads((HOST / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "mem0"
    assert manifest["hooks"] == "hooks.json"
    assert manifest["mcpServers"] == "mcp.json"

    mcp = json.loads((HOST / "mcp.json").read_text(encoding="utf-8"))
    server = mcp["mcpServers"]["mem0"]
    assert server["command"] == "python3"
    assert "${PLUGIN_ROOT}/core/mcp_server.py" in server["args"]


def test_native_copilot_bundle_is_self_contained(tmp_path: Path) -> None:
    root = build("copilot", "native", tmp_path / "copilot")

    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "mem0"
    assert (root / "hooks" / "adapter.py").is_file()
    assert (root / "core" / "mcp_server.py").is_file()
    assert (root / "core" / "_harness_id.py").is_file()
    assert (root / "skills" / "remember" / "SKILL.md").is_file()
    assert not (root / "agents").exists()
    assert not any(path.is_symlink() for path in root.rglob("*"))

    harness = (root / "core" / "_harness_id.py").read_text(encoding="utf-8")
    assert 'HARNESS_ID = "copilot"' in harness
    assert 'SOURCE_TAG = "COPILOT_PLUGIN"' in harness
    assert 'PLATFORM_APPLICATION = "copilot"' in harness


def test_user_prompt_injects_additional_context(monkeypatch, capsys) -> None:
    def fake_run(*_, **__):
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "UserPromptSubmit",
                        "additionalContext": "Important project memory: prefers TypeScript.",
                    }
                }
            )
        )
        return 0

    monkeypatch.setattr(adapter.hook_runner, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "userPromptSubmitted"])
    monkeypatch.setattr(
        sys,
        "stdin",
        io.StringIO(json.dumps({"sessionId": "sess-1", "cwd": "/repo", "prompt": "Hi"})),
    )

    exit_code = adapter.main()
    assert exit_code == 0

    captured = capsys.readouterr().out.strip()
    assert captured
    payload = json.loads(captured)
    assert payload["additionalContext"] == "Important project memory: prefers TypeScript."
    assert payload["hookSpecificOutput"]["hookEventName"] == "userPromptSubmitted"


def test_post_tool_failure_detection() -> None:
    store_calls = []

    def fake_record_tool(store, payload, failed=False):
        store_calls.append({"payload": payload, "failed": failed})

    adapter.record_tool = fake_record_tool

    # Successful call
    adapter._post_tool(None, {"tool_response": {"exitCode": 0, "output": "ok"}})
    assert len(store_calls) == 1
    assert store_calls[0]["failed"] is None or store_calls[0]["failed"] is False

    # Error payload
    adapter._post_tool(None, {"error": "Process timed out"})
    assert len(store_calls) == 2
    assert store_calls[1]["failed"] is True
    assert store_calls[1]["payload"]["error"] == "Process timed out"

    # Non-zero exit code inside tool_response
    adapter._post_tool(None, {"tool_response": {"exitCode": 1, "isError": True}})
    assert len(store_calls) == 3
    assert store_calls[2]["failed"] is True
