"""Exercise bundled subagent hooks as separate host processes, without Mem0 calls."""

import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))

from memory_core import EvidenceStore, RepoContext, checkpoint_stats  # noqa: E402


def test_generic_tracking_preserves_legacy_runs_and_can_finish_them(tmp_path):
    database = tmp_path / "evidence.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript("""
            CREATE TABLE sidekick_runs (
                repo_id TEXT NOT NULL, session_id TEXT NOT NULL,
                agent_id TEXT NOT NULL, agent_type TEXT NOT NULL,
                started_at TEXT NOT NULL, stopped_at TEXT, transcript_path TEXT,
                context_chars INTEGER NOT NULL DEFAULT 0, final_message TEXT,
                PRIMARY KEY(repo_id, session_id, agent_id)
            );
            INSERT INTO sidekick_runs VALUES
                ('repo', 'session', 'worker', 'default', '2026-09-10', NULL, NULL, 123, NULL);
        """)
    for _ in range(2):
        store = EvidenceStore(database)
        try:
            assert store.status("repo")["subagent_runs"] == 1
            row = store.conn.execute("SELECT * FROM sidekick_runs").fetchone()
            assert row["agent_id"] == "worker"
            assert row["context_chars"] == 123
            repo = RepoContext(str(tmp_path), str(tmp_path), "repo", "app", "main", "")
            store.stop_subagent(repo, "session", "worker", "default", "", "Completed after upgrade.")
            assert store.status("repo")["last_subagent"]["stopped_at"]
            assert store.conn.execute("SELECT final_message FROM sidekick_runs").fetchone()[0] == (
                "Completed after upgrade."
            )
        finally:
            store.close()
    assert checkpoint_stats([{"kind": "sidekick_stop", "payload": {"final_message": "Legacy result."}}]) == (0, 1, 14)


@pytest.mark.parametrize("host", ["claude-code", "codex"])
def test_subagent_hooks_preserve_parent_scope_and_correlate_completion(tmp_path, host):
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
    payload = {"session_id": "parent-session", "cwd": str(child), "agent_id": "worker", "agent_type": "default"}
    response_key = "last_assistant_message"
    if host == "codex":
        start, stop = "subagent-start", "subagent-stop"

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
    context = json.loads(output)["hookSpecificOutput"]["additionalContext"]
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
    assert runs[0]["context_chars"] > 0
