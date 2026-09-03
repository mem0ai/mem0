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

SPEC = importlib.util.spec_from_file_location("antigravity_adapter", HOST / "hooks" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def test_normalizes_antigravity_camel_case_payload(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "source": "USER_EXPLICIT",
                        "type": "USER_INPUT",
                        "status": "DONE",
                        "content": "<USER_REQUEST>\nremember the parser\n</USER_REQUEST>",
                    }
                ),
                json.dumps(
                    {
                        "source": "MODEL",
                        "type": "PLANNER_RESPONSE",
                        "status": "DONE",
                        "content": "The parser is fixed.",
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )
    value = adapter.normalize(
        {
            "conversationId": "conversation-1",
            "workspacePaths": ["/repo"],
            "transcriptPath": str(transcript),
            "toolCall": {"name": "run_command", "args": {"CommandLine": "pytest"}},
            "error": "failed",
        }
    )

    assert value["session_id"] == "conversation-1"
    assert value["cwd"] == "/repo"
    assert value["transcript_path"] == str(transcript)
    assert value["prompt"] == "remember the parser"
    assert value["last_assistant_message"] == "The parser is fixed."
    assert value["tool_name"] == "run_command"
    assert value["tool_input"] == {"CommandLine": "pytest"}
    assert value["tool_response"] == "failed"


def test_pre_invocation_translates_shared_recall_to_ephemeral_message(monkeypatch, capsys) -> None:
    calls = []

    def run_shared(arguments, payload):
        calls.append(arguments)
        if arguments == ["user-prompt"]:
            return 0, json.dumps(
                {"hookSpecificOutput": {"additionalContext": "Earlier repository context."}}
            )
        return 0, ""

    monkeypatch.setattr(adapter, "_run_shared", run_shared)
    monkeypatch.setattr(sys, "argv", ["adapter.py", "PreInvocation"])
    monkeypatch.setattr(sys, "stdin", io.StringIO('{"invocationNum": 0}'))

    assert adapter.main() == 0
    assert calls == [["session-start"], ["user-prompt"]]
    assert json.loads(capsys.readouterr().out) == {
        "injectSteps": [{"ephemeralMessage": "Earlier repository context."}]
    }


def test_native_antigravity_bundle_uses_supported_events(tmp_path: Path) -> None:
    root = build("antigravity", "native", tmp_path / "antigravity")

    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    hooks = json.loads((root / "hooks.json").read_text(encoding="utf-8"))["mem0"]
    assert manifest["$schema"] == "https://antigravity.google/schemas/v1/plugin.json"
    assert set(hooks) == {"PreInvocation", "PostToolUse", "Stop"}
    assert (root / "mcp_config.json").is_file()
    assert (root / "agents" / "sidekick" / "agent.md").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))
