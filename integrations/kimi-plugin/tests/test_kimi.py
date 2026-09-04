from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

HOST = Path(__file__).resolve().parents[1]
CORE_ROOT = HOST.parent / "agent-plugin-core"
sys.path.insert(0, str(CORE_ROOT))

from build.build import build  # noqa: E402

SPEC = importlib.util.spec_from_file_location("kimi_adapter", HOST / "hooks" / "adapter.py")
assert SPEC and SPEC.loader
adapter = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(adapter)


def _write_kimi_session(home: Path, session_id: str, records: list[dict]) -> Path:
    session = home / "sessions" / "wd_mem0_deadbeef1234" / session_id
    transcript = session / "agents" / "main" / "wire.jsonl"
    transcript.parent.mkdir(parents=True)
    transcript.write_text("\n".join(json.dumps(record) for record in records) + "\n", encoding="utf-8")
    (home / "session_index.jsonl").write_text(
        json.dumps({"sessionId": session_id, "sessionDir": str(session), "workDir": "/work/mem0"}) + "\n",
        encoding="utf-8",
    )
    return transcript


def test_stop_reads_main_response_from_kimi_session_transcript(tmp_path: Path, monkeypatch) -> None:
    transcript = _write_kimi_session(
        tmp_path,
        "session_abc",
        [
            {"type": "metadata", "protocol_version": "1.5", "created_at": 1788431400000},
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {"type": "step.begin", "uuid": "step-1", "turnId": "0", "step": 1},
                "time": 1788431400100,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {
                    "type": "content.part",
                    "stepUuid": "step-1",
                    "part": {"type": "text", "text": "Earlier answer."},
                },
                "time": 1788431400200,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {"type": "step.end", "uuid": "step-1", "finishReason": "end_turn"},
                "time": 1788431400300,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {"type": "step.begin", "uuid": "step-2", "turnId": "1", "step": 1},
                "time": 1788431400400,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {
                    "type": "content.part",
                    "stepUuid": "step-2",
                    "part": {"type": "think", "think": "Do not capture this reasoning."},
                },
                "time": 1788431400500,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {
                    "type": "content.part",
                    "stepUuid": "step-2",
                    "part": {"type": "text", "text": "Fixed and "},
                },
                "time": 1788431400600,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {
                    "type": "content.part",
                    "stepUuid": "step-2",
                    "part": {"type": "text", "text": "tested."},
                },
                "time": 1788431400700,
            },
            {
                "type": "context.append_loop_event",
                "agentId": "main",
                "event": {"type": "step.end", "uuid": "step-2", "finishReason": "end_turn"},
                "time": 1788431400800,
            },
        ],
    )
    monkeypatch.setenv("KIMI_CODE_HOME", str(tmp_path))

    value = adapter.normalize(
        {
            "hook_event_name": "Stop",
            "session_id": "session_abc",
            "session_title": "Fix Kimi capture",
            "client_type": "kimi_code_cli",
            "cwd": "/work/mem0",
            "stop_hook_active": False,
        }
    )

    assert value["last_assistant_message"] == "Fixed and tested."
    assert value["transcript_path"] == str(transcript)


def test_repeated_sidekick_invocations_get_distinct_run_ids(tmp_path: Path) -> None:
    store = adapter.hook_runner.EvidenceStore(tmp_path / "evidence.sqlite3")
    payload = {
        "hook_event_name": "SubagentStart",
        "session_id": "session_abc",
        "session_title": "Fix Kimi capture",
        "client_type": "kimi_code_cli",
        "cwd": str(tmp_path),
        "agent_name": "sidekick",
        "prompt": "Fix the adapter",
    }

    try:
        adapter._sidekick_start(store, adapter.normalize(payload))
        adapter._sidekick_start(store, adapter.normalize(payload))
        adapter._sidekick_stop(
            store,
            adapter.normalize(
                {
                    **payload,
                    "hook_event_name": "SubagentStop",
                    "response": "First run complete.",
                }
            ),
        )
        adapter._sidekick_stop(
            store,
            adapter.normalize(
                {
                    **payload,
                    "hook_event_name": "SubagentStop",
                    "response": "Second run complete.",
                }
            ),
        )

        rows = store.conn.execute(
            "SELECT agent_id, stopped_at, final_message FROM sidekick_runs ORDER BY started_at, agent_id"
        ).fetchall()
    finally:
        store.close()

    assert len(rows) == 2
    assert rows[0]["agent_id"] != rows[1]["agent_id"]
    assert all(row["stopped_at"] for row in rows)
    assert {row["final_message"] for row in rows} == {"First run complete.", "Second run complete."}


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
