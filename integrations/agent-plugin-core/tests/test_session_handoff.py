from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

CORE = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(CORE))

import handoff_engine as engine  # noqa: E402
from handoff_sources import _messages_items, read_source  # noqa: E402


def message(role, text):
    return {
        "type": "message",
        "role": role,
        "content": [{"type": "input_text" if role == "user" else "output_text", "text": text}],
    }


def envelope(tmp_path, items=None):
    return {
        "format": "mem0.session-handoff.v1",
        "source": {"host": "pi-agent", "session_id": "s1", "cwd": str(tmp_path), "title": "Continue the task"},
        "items": items or [message("user", "Continue here"), message("assistant", "Ready")],
    }


def transcript(tmp_path, records):
    path = tmp_path / "session.jsonl"
    path.write_text("".join(json.dumps(record) + "\n" for record in records))
    return path


def test_neutral_stdin_save_round_trip_without_models(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(engine, "DEFAULT_BUNDLE_DIR", tmp_path / "handoffs")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(envelope(tmp_path))))
    assert engine.main(["--save", "--bundle", "-"]) == 0
    destination = Path(json.loads(capsys.readouterr().out)["resource"])
    plan = engine.load_bundle(destination)
    assert plan.source.host == "pi-agent"
    assert plan.source.title == "Continue the task"
    assert plan.items == envelope(tmp_path)["items"]
    assert destination.stat().st_mode & 0o777 == 0o600


@pytest.mark.parametrize(
    "item",
    [
        {"type": "message", "role": "system", "content": [{"type": "input_text", "text": "privileged"}]},
        {
            "type": "message",
            "role": "assistant",
            "status": "incomplete",
            "content": [{"type": "output_text", "text": "partial"}],
        },
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_image", "image_url": "https://example.com/not-local.png"}],
        },
        {"type": "function_call", "call_id": "pending", "name": "Read", "arguments": "{}"},
        {"type": "function_call_output", "call_id": "missing", "output": "result"},
        {"type": "unknown"},
    ],
)
def test_neutral_boundary_rejects_unsupported_or_incomplete_items(tmp_path, item):
    with pytest.raises(engine.HandoffError):
        engine.plan_from_bundle(envelope(tmp_path, [message("user", "Task"), item]))


def test_neutral_missing_tool_name_is_restored_and_host_path_is_validated(tmp_path):
    payload = envelope(
        tmp_path,
        [
            message("user", "Task"),
            {"type": "function_call", "call_id": "c1", "name": "Read", "arguments": "{}"},
            {"type": "function_call_output", "call_id": "c1", "output": "Complete output"},
        ],
    )
    plan = engine.plan_from_bundle(payload)
    assert plan.items[-1]["name"] == "Read"
    payload["source"]["host"] = "../../escape"
    with pytest.raises(engine.HandoffError, match="invalid source"):
        engine.plan_from_bundle(payload)


def test_neutral_project_resolves_git_root_for_nested_cwd(tmp_path, monkeypatch):
    nested = tmp_path / "nested"
    nested.mkdir()
    payload = envelope(nested)
    plan = engine.plan_from_bundle(payload)
    monkeypatch.setattr(engine, "_git_root", lambda cwd: str(tmp_path))
    assert engine._with_cwd(plan, None).source.project_cwd == str(tmp_path)
    assert engine._with_cwd(plan, nested).source.project_cwd == str(tmp_path)


def test_codex_native_rollout_keeps_response_items_and_excludes_harness(tmp_path):
    # openai/codex: codex-rs/protocol/src/protocol.rs and persisted response_item payloads.
    records = [
        {"type": "session_meta", "payload": {"id": "codex-session", "cwd": str(tmp_path)}},
        {"type": "world_state", "payload": {"full": True, "state": {"agents_md": {"text": "harness config"}}}},
        {"type": "token_usage_record", "payload": {"input_tokens": 123, "output_tokens": 45}},
        {"type": "response_item", "payload": message("developer", "harness config")},
        {"type": "response_item", "payload": {"type": "reasoning", "encrypted_content": "opaque"}},
        {"type": "response_item", "payload": message("user", "Keep user")},
        {"type": "response_item", "payload": message("assistant", "Keep answer")},
        {"type": "event_msg", "payload": {"type": "agent_message", "message": "duplicate UI text"}},
    ]
    plan = read_source("codex", transcript(tmp_path, records))
    assert plan.source.session_id == "codex-session"
    assert len(plan.items) == 2
    assert "harness config" not in json.dumps(plan.items)
    assert "duplicate UI text" not in json.dumps(plan.items)


@pytest.mark.parametrize(
    "record",
    [
        {"type": "compacted", "payload": {"message": "opaque summary"}},
        {"type": "response_item", "payload": {"type": "compaction", "encrypted_content": "opaque"}},
        {"type": "event_msg", "payload": {"type": "thread_rolled_back", "num_turns": 1}},
    ],
)
def test_codex_opaque_compaction_and_rollback_fail(tmp_path, record):
    records = [{"type": "response_item", "payload": message("user", "Task")}, record]
    with pytest.raises(engine.HandoffError):
        read_source("codex", transcript(tmp_path, records), cwd=tmp_path)


def test_cursor_native_text_and_tool_records_keep_all_evidence(tmp_path):
    # Cursor native role/message.content JSONL; missing tool outputs are rejected.
    records = [
        {"role": "user", "message": {"content": [{"type": "text", "text": "Inspect"}]}},
        {
            "role": "assistant",
            "message": {"content": [{"type": "tool_use", "id": "c1", "name": "Read", "input": {"path": "file.py"}}]},
        },
        {"role": "user", "message": {"content": [{"type": "tool_result", "tool_use_id": "c1", "content": "x" * 6000}]}},
        {"role": "assistant", "message": {"content": [{"type": "text", "text": "Finished"}]}},
    ]
    plan = read_source("cursor", transcript(tmp_path, records), cwd=tmp_path, title="Cursor task")
    assert plan.source.host == "cursor"
    assert plan.source.title == "Cursor task"
    assert plan.items[2]["output"] == "x" * 6000
    with pytest.raises(engine.HandoffError, match="unfinished"):
        read_source("cursor", transcript(tmp_path, records[:2]), cwd=tmp_path)


def test_antigravity_native_completed_text_steps(tmp_path):
    # Existing native adapter fixture; public paths: https://www.antigravity.google/docs/hooks
    records = [
        {
            "type": "USER_INPUT",
            "source": "USER_EXPLICIT",
            "status": "DONE",
            "content": "<USER_REQUEST>Do work</USER_REQUEST>",
        },
        {"type": "PLANNER_RESPONSE", "source": "MODEL", "status": "DONE", "content": "Done"},
    ]
    plan = read_source("antigravity", transcript(tmp_path, records), cwd=tmp_path)
    assert "<USER_REQUEST>Do work</USER_REQUEST>" in json.dumps(plan.items)
    assert plan.items[1]["content"][0]["text"] == "Done"
    records[-1]["status"] = "RUNNING"
    with pytest.raises(engine.HandoffError, match="unfinished"):
        read_source("antigravity", transcript(tmp_path, records), cwd=tmp_path)


def test_kimi_native_wire_stream_and_compaction(tmp_path):
    # MoonshotAI/kimi-code: apps/vis/server/test/fixtures/sessions/sample-main/agents/main/wire.jsonl
    # and packages/agent-core-v2/src/agent/contextMemory/{loopEventFold,compactionHandoff}.ts
    records = [
        {"type": "metadata", "protocol_version": "1.5"},
        {"type": "config.update", "cwd": str(tmp_path)},
        {
            "type": "context.append_message",
            "message": {"role": "user", "content": [{"type": "text", "text": "Original user"}]},
        },
        {"type": "context.append_loop_event", "event": {"type": "step.begin", "uuid": "s1"}},
        {
            "type": "context.append_loop_event",
            "event": {"type": "content.part", "stepUuid": "s1", "part": {"type": "text", "text": "Original answer"}},
        },
        {"type": "context.append_loop_event", "event": {"type": "step.end", "uuid": "s1", "finishReason": "end_turn"}},
        {
            "type": "context.apply_compaction",
            "summary": "Native summary",
            "compactedCount": 2,
            "keptUserMessageCount": 1,
        },
        {
            "type": "context.append_message",
            "message": {"role": "user", "content": [{"type": "text", "text": "Continue"}]},
        },
    ]
    plan = read_source("kimi", transcript(tmp_path, records))
    assert [item["content"][0]["text"] for item in plan.items] == [
        "Original user",
        "Native summary",
        "<system-reminder>\nContext compaction is complete — continue the work that was in progress when it began.\n</system-reminder>",
        "Continue",
    ]
    assert "Original answer" not in json.dumps(plan.items)
    records.append({"type": "context.undo", "count": 1})
    with pytest.raises(engine.HandoffError, match="active-context"):
        read_source("kimi", transcript(tmp_path, records))


def test_kimi_native_tool_events_and_unfinished_turn(tmp_path):
    records = [
        {"type": "config.update", "cwd": str(tmp_path)},
        {
            "type": "context.append_message",
            "message": {"role": "user", "content": [{"type": "text", "text": "Inspect"}]},
        },
        {"type": "context.append_loop_event", "event": {"type": "step.begin", "uuid": "s1"}},
        {
            "type": "context.append_loop_event",
            "event": {
                "type": "tool.call",
                "stepUuid": "s1",
                "toolCallId": "c1",
                "name": "Read",
                "args": {"path": "a.py"},
            },
        },
        {
            "type": "context.append_loop_event",
            "event": {"type": "tool.result", "toolCallId": "c1", "result": {"output": "contents", "isError": True}},
        },
        {"type": "context.append_loop_event", "event": {"type": "step.end", "uuid": "s1", "finishReason": "tool_use"}},
    ]
    plan = read_source("kimi", transcript(tmp_path, records))
    assert plan.items[1]["name"] == "Read"
    assert plan.items[2]["output"] == [{"type": "text", "text": "Tool failed."}, {"type": "text", "text": "contents"}]
    with pytest.raises(engine.HandoffError, match="streaming"):
        read_source("kimi", transcript(tmp_path, records[:-1]))


@pytest.mark.parametrize("compactions", [2, 3])
def test_kimi_repeated_compaction_replaces_previous_continuation(tmp_path, compactions):
    records = [
        {"type": "config.update", "cwd": str(tmp_path)},
        {
            "type": "context.append_message",
            "message": {"role": "user", "content": [{"type": "text", "text": "Original user"}]},
        },
    ]
    for index in range(compactions):
        records.append({
            "type": "context.apply_compaction",
            "summary": f"Native summary {index + 1}",
            "compactedCount": 1 if index == 0 else 3,
            "keptUserMessageCount": 1,
        })

    plan = read_source("kimi", transcript(tmp_path, records))

    # Native Kimi marks the continuation as an injection, excluded by the next compaction.
    assert [item["content"][0]["text"] for item in plan.items] == [
        "Original user",
        f"Native summary {compactions}",
        "<system-reminder>\nContext compaction is complete — continue the work that was in progress when it began.\n</system-reminder>",
    ]


@pytest.mark.parametrize("host", ["pi-agent", "openclaw"])
@pytest.mark.parametrize("latest_title", ["Renamed title", ""])
def test_pi_title_is_session_wide_after_branching(tmp_path, host, latest_title):
    records = [
        {"type": "session", "id": "native-session", "cwd": str(tmp_path)},
        {"id": "old-title", "parentId": None, "type": "session_info", "name": "Original title"},
        {"id": "new-title", "parentId": "old-title", "type": "session_info", "name": latest_title},
        {
            "id": "branch",
            "parentId": "old-title",
            "type": "message",
            "message": {"role": "user", "content": "Continue on another branch"},
        },
    ]

    plan = read_source(host, transcript(tmp_path, records))

    # SessionManager.getSessionName scans all entries, including title clears on other branches.
    assert plan.source.title == (latest_title or f"{host} session session")
    assert plan.items == [message("user", "Continue on another branch")]


def test_openclaw_active_branch_compaction_and_original_title(tmp_path):
    # Pi native session-manager.buildSessionContext and messages.convertToLlm, used by OpenClaw.
    records = [
        {"type": "session", "id": "native-session", "cwd": str(tmp_path)},
        {"id": "title", "parentId": None, "type": "session_info", "name": "Original title"},
        {"id": "u1", "parentId": "title", "type": "message", "message": {"role": "user", "content": "Discarded"}},
        {
            "id": "abandoned",
            "parentId": "u1",
            "type": "message",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Wrong branch"}]},
        },
        {"id": "u2", "parentId": "u1", "type": "message", "message": {"role": "user", "content": "Keep user"}},
        {
            "id": "compact",
            "parentId": "u2",
            "type": "compaction",
            "summary": "Native summary",
            "firstKeptEntryId": "u2",
        },
        {
            "id": "a1",
            "parentId": "compact",
            "type": "message",
            "message": {"role": "assistant", "content": [{"type": "text", "text": "Continue"}]},
        },
    ]
    plan = read_source("openclaw", transcript(tmp_path, records))
    assert plan.source.title == "Original title"
    assert plan.source.session_id == "native-session"
    assert "Native summary" in plan.items[0]["content"][0]["text"]
    assert "Keep user" in json.dumps(plan.items)
    assert "Discarded" not in json.dumps(plan.items)
    assert "Wrong branch" not in json.dumps(plan.items)


def test_inline_tool_order_is_preserved():
    items = _messages_items(
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "before"},
                    {"type": "toolCall", "id": "c1", "name": "Read", "arguments": {}},
                    {"type": "text", "text": "after"},
                ],
            }
        ],
        [],
    )
    assert [item["type"] for item in items] == ["message", "function_call", "message"]
    assert items[0]["content"][0]["text"] == "before"
    assert items[2]["content"][0]["text"] == "after"


def test_generic_cli_requires_source_and_accepts_native_openclaw(tmp_path, monkeypatch, capsys):
    path = transcript(
        tmp_path,
        [
            {"type": "session", "id": "s1", "cwd": str(tmp_path)},
            {"type": "message", "id": "u1", "parentId": None, "message": {"role": "user", "content": "Task"}},
        ],
    )
    monkeypatch.setattr(engine, "DEFAULT_BUNDLE_DIR", tmp_path / "handoffs")
    assert engine.main(["--save", "--session", str(path)], default_source=None) == 1
    assert "--source is required" in capsys.readouterr().err
    assert engine.main(["--save", "--source", "openclaw", "--session", str(path)], default_source=None) == 0
    assert json.loads(capsys.readouterr().out)["source_host"] == "openclaw"


@pytest.mark.parametrize(
    "patch",
    [
        {"status": []},
        {"type": {}},
        {"role": []},
        {"content": [{"type": []}]},
    ],
)
def test_malformed_neutral_item_returns_handoff_error(tmp_path, patch):
    item = {**message("user", "Task"), **patch}
    with pytest.raises(engine.HandoffError):
        engine.plan_from_bundle(envelope(tmp_path, [item]))


@pytest.mark.parametrize(
    "kind,source",
    [
        ("PLANNER_THOUGHT", "MODEL"),
        ("HARNESS_CONTEXT", "SYSTEM"),
        ("UNKNOWN_TOOL", "TOOL"),
    ],
)
def test_antigravity_unverified_steps_never_become_visible_messages(tmp_path, kind, source):
    records = [
        {"type": "USER_INPUT", "source": "USER_EXPLICIT", "status": "DONE", "content": "Do work"},
        {"type": kind, "source": source, "status": "DONE", "content": "Unverified internal data"},
    ]
    with pytest.raises(engine.HandoffError, match="Unsupported Antigravity step"):
        read_source("antigravity", transcript(tmp_path, records), cwd=tmp_path)
