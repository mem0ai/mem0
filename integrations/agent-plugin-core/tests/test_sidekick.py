"""Exercise bundled subagent hooks as separate host processes, without Mem0 calls."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from memory_core import EvidenceStore  # noqa: E402


@pytest.mark.parametrize("host", ["claude-code", "codex", "kimi", "cursor"])
def test_sidekick_hooks_preserve_parent_scope_and_correlate_completion(tmp_path, host):
    parent = tmp_path / "parent"
    child = tmp_path / "child-worktree"
    parent.mkdir()
    child.mkdir()
    database = tmp_path / "data" / "evidence.sqlite3"
    store = EvidenceStore(database)
    repo = store.repo_for_session("parent-session", str(parent))
    store.mark_injected("parent-session", repo.identity, [{"id": "one", "memory": "Parent memory marker."}])
    store.mark_injected("other-session", repo.identity, [{"id": "two", "memory": "Foreign memory marker."}])
    store.close()

    plugin = ROOT.parent / f"{host}-plugin"
    adapter = plugin / ("adapters/claude/hook.py" if host == "claude-code" else "hooks/adapter.py")
    start, stop = "sidekick-start", "sidekick-stop"
    payload = {"session_id": "parent-session", "cwd": str(child), "agent_id": "worker", "agent_type": "sidekick"}
    response_key = "last_assistant_message"
    if host == "kimi":
        start, stop = "SubagentStart", "SubagentStop"
        payload["agent_name"] = payload.pop("agent_type")
        response_key = "response"
    elif host == "cursor":
        start, stop = "subagentStart", "subagentStop"
        payload = {
            "conversation_id": "parent-session",
            "workspace_roots": [str(child)],
            "subagent_id": "worker",
            "subagent_type": "sidekick",
        }
        response_key = "summary"

    env = {key: value for key, value in os.environ.items() if not key.startswith(("MEM0_", "CLAUDE_PLUGIN_"))}
    env.update(MEM0_CODE_DATA_DIR=str(database.parent), MEM0_TELEMETRY="false", MEM0_API_URL="http://127.0.0.1:1")

    def invoke(event, body):
        result = subprocess.run(
            [sys.executable, str(adapter), event],
            input=json.dumps({**body, "hook_event_name": event}),
            text=True,
            capture_output=True,
            env=env,
            timeout=15,
            check=True,
        )
        return result.stdout

    output = invoke(start, payload)
    if host == "cursor":
        assert json.loads(output) == {"permission": "allow"}
    else:
        context = output if host == "kimi" else json.loads(output)["hookSpecificOutput"]["additionalContext"]
        assert "Parent memory marker." in context
    assert "Foreign memory marker." not in output
    assert "Parent memory marker." not in invoke(start, payload)
    invoke(stop, {**payload, response_key: "Finished the delegated task."})

    store = EvidenceStore(database)
    runs = store.conn.execute("SELECT * FROM sidekick_runs").fetchall()
    store.close()
    assert len(runs) == 1
    assert (runs[0]["repo_id"], runs[0]["session_id"], runs[0]["agent_id"]) == (
        repo.identity, "parent-session", "worker"
    )
    assert runs[0]["stopped_at"]
    assert runs[0]["final_message"] == "Finished the delegated task."
    assert (runs[0]["context_chars"] > 0) == (host != "cursor")
