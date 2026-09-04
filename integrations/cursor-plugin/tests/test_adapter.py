from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))
from build.build import build  # noqa: E402

SPEC = importlib.util.spec_from_file_location("cursor_adapter", HOST / "hooks" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


@pytest.mark.parametrize(
    ("event", "action"),
    [
        ("sessionStart", "session-start"),
        ("beforeSubmitPrompt", "user-prompt"),
        ("postToolUse", "post-tool"),
        ("postToolUseFailure", "post-tool-failure"),
        ("afterAgentResponse", "assistant-stop"),
        ("subagentStart", "sidekick-start"),
        ("subagentStop", "sidekick-stop"),
        ("stop", "stop"),
        ("sessionEnd", "session-end"),
        ("preCompact", "pre-compact"),
    ],
)
def test_normalizes_cursor_events(event: str, action: str) -> None:
    normalized = adapter.normalize(
        {
            "conversation_id": "conversation-1",
            "workspace_roots": ["/worktree"],
            "tool_output": "done",
            "text": "assistant response",
        },
        event,
    )

    assert normalized["action"] == action
    assert normalized["payload"]["session_id"] == "conversation-1"
    assert normalized["payload"]["cwd"] == "/worktree"
    assert normalized["payload"]["tool_response"] == "done"
    assert normalized["payload"]["last_assistant_message"] == "assistant response"


def test_after_agent_response_does_not_return_internal_context(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter.hook_runner, "default_record_stop", lambda store, payload: (object(), "session"))

    assert adapter._record_response(object(), {}) is None


def test_normalizes_cursor_sidekick_fields() -> None:
    started = adapter.normalize(
        {
            "subagent_id": "agent-1",
            "subagent_type": "sidekick",
            "parent_conversation_id": "parent-1",
        },
        "subagentStart",
    )["payload"]
    stopped = adapter.normalize({"summary": "done"}, "subagentStop")["payload"]

    assert started["agent_id"] == "agent-1"
    assert started["agent_type"] == "sidekick"
    assert started["session_id"] == "parent-1"
    assert stopped["last_assistant_message"] == "done"


def test_cursor_sidekick_records_lifecycle_without_blocking(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(adapter, "record_sidekick_start", lambda store, payload: "unused cursor context")
    stopped = []
    monkeypatch.setattr(adapter, "record_sidekick_stop", lambda store, payload: stopped.append(payload))

    assert adapter._record_sidekick_start(object(), {}) == {"permission": "allow"}
    assert adapter._record_sidekick_stop(object(), {"summary": "done"}) is None
    assert stopped == [{"summary": "done"}]


def test_cursor_hooks_use_native_flat_entries() -> None:
    hooks = json.loads((HOST / "hooks" / "hooks.json").read_text(encoding="utf-8"))

    assert hooks["version"] == 1
    assert set(hooks["hooks"]) >= {
        "sessionStart",
        "beforeSubmitPrompt",
        "postToolUse",
        "subagentStart",
        "subagentStop",
        "stop",
        "sessionEnd",
    }
    assert hooks["hooks"]["subagentStart"][0]["matcher"] == "^sidekick$"
    assert hooks["hooks"]["subagentStop"][0]["matcher"] == "^sidekick$"
    assert all("hooks" not in entry for entries in hooks["hooks"].values() for entry in entries)


def test_native_cursor_bundle_is_self_contained(tmp_path: Path) -> None:
    root = build("cursor", "native", tmp_path / "cursor")

    manifest = json.loads((root / ".cursor-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["hooks"] == "./hooks/hooks.json"
    assert (root / "hooks" / "adapter.py").is_file()
    assert (root / "agents" / "sidekick.md").is_file()
    assert not any(path.is_symlink() for path in root.rglob("*"))
