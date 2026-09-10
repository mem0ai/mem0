from __future__ import annotations

import base64
import hashlib
import json
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "python"
sys.path.insert(0, str(SCRIPTS))

import claude_to_codex  # noqa: E402


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record) + "\n" for record in records),
        encoding="utf-8",
    )


def _record(
    uuid: str,
    parent: str | None,
    record_type: str,
    *,
    content=None,
    **extra,
) -> dict:
    record = {
        "uuid": uuid,
        "parentUuid": parent,
        "sessionId": "session-1",
        "cwd": "/tmp",
        "isSidechain": False,
        "type": record_type,
        **extra,
    }
    if content is not None:
        record["message"] = {"role": record_type, "content": content}
    return record


def test_build_plan_uses_latest_compaction_and_active_branch(tmp_path):
    session = tmp_path / "session-1.jsonl"
    records = [
        {
            "type": "custom-title",
            "customTitle": "Memory Testing",
            "sessionId": "session-1",
        },
        _record("old-user", None, "user", content="Discarded request"),
        _record(
            "old-answer",
            "old-user",
            "assistant",
            content=[{"type": "text", "text": "Discarded answer"}],
        ),
        _record(
            "boundary",
            "old-answer",
            "system",
            subtype="compact_boundary",
            content=None,
        ),
        _record(
            "summary",
            "boundary",
            "user",
            content="Claude's own compact summary",
            isCompactSummary=True,
        ),
        _record(
            "preserved",
            "summary",
            "assistant",
            content=[{"type": "text", "text": "Preserved conclusion"}],
        ),
        _record("new-user", "preserved", "user", content="Continue the task"),
        _record(
            "new-answer",
            "new-user",
            "assistant",
            content=[{"type": "text", "text": "Current answer"}],
        ),
        _record(
            "abandoned",
            "old-answer",
            "assistant",
            content=[{"type": "text", "text": "Abandoned branch"}],
        ),
        _record(
            "leaf",
            "new-answer",
            "assistant",
            content=[{"type": "text", "text": "Active leaf"}],
        ),
    ]
    _write(session, records)

    plan = claude_to_codex.build_plan(str(session), tmp_path)

    assert plan.source.title == "Memory Testing"
    assert plan.source.leaf_uuid == "leaf"
    assert plan.source.compact_boundary_uuid == "boundary"
    serialized = json.dumps(plan.items)
    assert "Claude's own compact summary" in serialized
    assert "Preserved conclusion" in serialized
    assert "Active leaf" in serialized
    assert "Discarded request" not in serialized
    assert "Abandoned branch" not in serialized


def test_build_plan_keeps_starting_project_when_tool_changes_cwd(tmp_path):
    session = tmp_path / "session-1.jsonl"
    records = [
        _record("u1", None, "user", content="Work in this project"),
        _record(
            "a1",
            "u1",
            "assistant",
            content=[
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "Bash",
                    "input": {"command": "cd /tmp/nested && pwd"},
                }
            ],
        ),
        _record(
            "r1",
            "a1",
            "user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "content": "/tmp/nested",
                }
            ],
            cwd="/tmp/nested",
        ),
        _record(
            "a2",
            "r1",
            "assistant",
            content=[{"type": "text", "text": "Done"}],
            cwd="/tmp/nested",
        ),
    ]
    _write(session, records)

    plan = claude_to_codex.build_plan(str(session), tmp_path)

    assert plan.source.cwd == str(Path("/tmp").resolve())


def test_tool_calls_results_attachments_and_hidden_reasoning(tmp_path):
    session = tmp_path / "session-1.jsonl"
    records = [
        {"type": "custom-title", "customTitle": "Tools", "sessionId": "session-1"},
        _record("u1", None, "user", content="Inspect the file"),
        _record(
            "a1",
            "u1",
            "assistant",
            content=[
                {"type": "thinking", "thinking": "private reasoning"},
                {"type": "text", "text": "I will inspect it."},
                {
                    "type": "tool_use",
                    "id": "call-1",
                    "name": "Read",
                    "input": {"file_path": "a.py"},
                },
            ],
        ),
        _record(
            "r1",
            "a1",
            "user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": "call-1",
                    "content": "print('ok')",
                }
            ],
        ),
        {
            "uuid": "attachment",
            "parentUuid": "r1",
            "sessionId": "session-1",
            "cwd": "/tmp",
            "isSidechain": False,
            "type": "attachment",
            "attachment": {
                "type": "file",
                "filename": "a.py",
                "content": {
                    "type": "text",
                    "file": {"filePath": "/tmp/a.py", "content": "print('ok')"},
                },
            },
        },
        _record(
            "a2",
            "attachment",
            "assistant",
            content=[{"type": "text", "text": "The file prints ok."}],
        ),
    ]
    _write(session, records)

    plan = claude_to_codex.build_plan(str(session), tmp_path)

    assert plan.hidden_reasoning_blocks_skipped == 1
    assert not any("private reasoning" in json.dumps(item) for item in plan.items)
    call = next(item for item in plan.items if item["type"] == "function_call")
    result = next(item for item in plan.items if item["type"] == "function_call_output")
    assert call == {
        "type": "function_call",
        "call_id": "call-1",
        "name": "Read",
        "arguments": '{"file_path":"a.py"}',
    }
    assert result["call_id"] == "call-1"
    assert result["output"] == "print('ok')"
    assert any("<claude_attachment" in json.dumps(item) for item in plan.items)


def test_claude_harness_attachments_are_not_imported_as_user_messages(tmp_path):
    session = tmp_path / "session-1.jsonl"
    records = [
        _record("u1", None, "user", content="Continue the project"),
        {
            "uuid": "skills",
            "parentUuid": "u1",
            "sessionId": "session-1",
            "cwd": "/tmp",
            "isSidechain": False,
            "type": "attachment",
            "attachment": {
                "type": "skill_listing",
                "content": "Claude-only skill instructions",
            },
        },
        {
            "uuid": "tokens",
            "parentUuid": "skills",
            "sessionId": "session-1",
            "cwd": "/tmp",
            "isSidechain": False,
            "type": "attachment",
            "attachment": {
                "type": "total_tokens_reminder",
                "text": "15000000 tokens left",
            },
        },
        _record(
            "a1",
            "tokens",
            "assistant",
            content=[{"type": "text", "text": "The project is ready."}],
        ),
    ]
    _write(session, records)

    plan = claude_to_codex.build_plan(str(session), tmp_path)
    serialized = json.dumps(plan.items)

    assert "Continue the project" in serialized
    assert "The project is ready" in serialized
    assert "skill_listing" not in serialized
    assert "Claude-only skill instructions" not in serialized
    assert "total_tokens_reminder" not in serialized


def test_unfinished_tool_call_fails(tmp_path):
    session = tmp_path / "session-1.jsonl"
    _write(
        session,
        [
            _record("u1", None, "user", content="Inspect"),
            _record(
                "a1",
                "u1",
                "assistant",
                content=[{"type": "tool_use", "id": "call-1", "name": "Read", "input": {}}],
            ),
        ],
    )

    with pytest.raises(claude_to_codex.HandoffError, match="unfinished tool call"):
        claude_to_codex.build_plan(str(session), tmp_path)


def test_parallel_tool_results_from_sibling_records_are_restored(tmp_path):
    session = tmp_path / "session-1.jsonl"
    records = [
        _record("u1", None, "user", content="Inspect both files"),
        _record(
            "call-a-record",
            "u1",
            "assistant",
            content=[
                {
                    "type": "tool_use",
                    "id": "call-a",
                    "name": "Read",
                    "input": {"file_path": "a.py"},
                }
            ],
        ),
        _record(
            "call-b-record",
            "call-a-record",
            "assistant",
            content=[
                {
                    "type": "tool_use",
                    "id": "call-b",
                    "name": "Read",
                    "input": {"file_path": "b.py"},
                }
            ],
        ),
        _record(
            "result-a",
            "call-a-record",
            "user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": "call-a",
                    "content": "a contents",
                }
            ],
        ),
        _record(
            "result-b",
            "call-b-record",
            "user",
            content=[
                {
                    "type": "tool_result",
                    "tool_use_id": "call-b",
                    "content": "b contents",
                }
            ],
        ),
        _record(
            "final",
            "result-b",
            "assistant",
            content=[{"type": "text", "text": "Both files are understood."}],
        ),
    ]
    _write(session, records)

    plan = claude_to_codex.build_plan(str(session), tmp_path)

    results = [item for item in plan.items if item["type"] == "function_call_output"]
    assert {item["call_id"] for item in results} == {"call-a", "call-b"}
    assert sum(item["call_id"] == "call-b" for item in results) == 1


def test_missing_tool_call_for_result_fails(tmp_path):
    session = tmp_path / "session-1.jsonl"
    _write(
        session,
        [
            _record(
                "r1",
                None,
                "user",
                content=[
                    {
                        "type": "tool_result",
                        "tool_use_id": "missing",
                        "content": "result",
                    }
                ],
            )
        ],
    )

    with pytest.raises(claude_to_codex.HandoffError, match="no matching call"):
        claude_to_codex.build_plan(str(session), tmp_path)


def test_partial_jsonl_fails(tmp_path):
    session = tmp_path / "session-1.jsonl"
    session.write_text('{"type":"user"}', encoding="utf-8")

    with pytest.raises(claude_to_codex.HandoffError, match="incomplete"):
        claude_to_codex.build_plan(str(session), tmp_path)


def test_bundle_is_private(tmp_path):
    session = tmp_path / "session-1.jsonl"
    _write(
        session,
        [
            _record("u1", None, "user", content="Question"),
            _record("a1", "u1", "assistant", content=[{"type": "text", "text": "Answer"}]),
        ],
    )
    plan = claude_to_codex.build_plan(str(session), tmp_path)
    bundle = claude_to_codex.write_bundle(plan, tmp_path / "private" / "handoff.json")

    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600
    assert json.loads(bundle.read_text())["format"] == claude_to_codex.FORMAT_VERSION

    restored = claude_to_codex.load_bundle(bundle)
    assert restored.source == plan.source
    assert restored.items == plan.items
    assert restored.approximate_tokens == plan.approximate_tokens


def test_explicit_cwd_can_relocate_a_session(tmp_path):
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd="/path/that/no/longer/exists",
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
        ),
        items=[{"type": "message", "role": "user", "content": []}],
        source_records=1,
        active_records=1,
        imported_records=1,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=10,
        warnings=[],
    )

    relocated = claude_to_codex._with_cwd(plan, tmp_path)

    assert relocated.source.cwd == "/path/that/no/longer/exists"
    assert relocated.source.codex_cwd == str(tmp_path.resolve())


def test_native_import_records_preserve_complete_tools_as_visible_text(tmp_path):
    output = "x" * 6_000
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd=str(tmp_path),
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
            codex_cwd=str(tmp_path),
        ),
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Inspect it"}],
            },
            {
                "type": "function_call",
                "call_id": "call-1",
                "name": "Read",
                "arguments": '{"file_path":"a.py"}',
            },
            {
                "type": "function_call_output",
                "call_id": "call-1",
                "name": "Read",
                "output": output,
            },
        ],
        source_records=3,
        active_records=3,
        imported_records=3,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=1_600,
        warnings=[],
    )

    records = claude_to_codex._native_import_records(plan, tmp_path / "assets")

    assert records[0]["customTitle"] == "Task"
    assert records[1]["type"] == "user"
    assert records[1]["cwd"] == str(tmp_path)
    assert records[2]["type"] == "assistant"
    assert '<tool_call name="Read" id="call-1">' in records[2]["message"]["content"]
    assert records[3]["type"] == "assistant"
    assert output in records[3]["message"]["content"]


def test_native_import_saves_message_images_once_and_references_them(tmp_path):
    image = b"same exact image"
    encoded = base64.b64encode(image).decode()
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd=str(tmp_path),
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
            codex_cwd=str(tmp_path),
        ),
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": "Before"},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{encoded}",
                    },
                    {"type": "input_text", "text": "Between"},
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{encoded}",
                    },
                    {"type": "input_text", "text": "After"},
                ],
            }
        ],
        source_records=1,
        active_records=1,
        imported_records=1,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=10,
        warnings=[],
    )
    asset_dir = tmp_path / "assets"

    records = claude_to_codex._native_import_records(plan, asset_dir)

    saved = list(asset_dir.iterdir())
    assert len(saved) == 1
    assert saved[0].name == f"{hashlib.sha256(image).hexdigest()}.png"
    assert saved[0].read_bytes() == image
    content = records[1]["message"]["content"]
    reference = f"[Image saved at {saved[0]}]"
    assert content == f"Before\n\n{reference}\n\nBetween\n\n{reference}\n\nAfter"


def test_native_import_preserves_text_around_tool_result_image(tmp_path):
    image = b"tool image"
    encoded = base64.b64encode(image).decode()
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd=str(tmp_path),
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
            codex_cwd=str(tmp_path),
        ),
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "Inspect it"}],
            },
            {
                "type": "function_call_output",
                "call_id": "call-1",
                "name": "Browser",
                "output": [
                    {"type": "text", "text": "Before"},
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": encoded,
                        },
                    },
                    {"type": "text", "text": "After"},
                ],
            },
        ],
        source_records=2,
        active_records=2,
        imported_records=2,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=10,
        warnings=[],
    )
    asset_dir = tmp_path / "assets"

    records = claude_to_codex._native_import_records(plan, asset_dir)

    saved = next(asset_dir.iterdir())
    output = records[2]["message"]["content"]
    assert f"Before\n[Image saved at {saved}]\nAfter" in output
    assert encoded not in output


def test_native_import_rejects_invalid_image_data(tmp_path):
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd=str(tmp_path),
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
            codex_cwd=str(tmp_path),
        ),
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": "data:image/png;base64,not-base64",
                    }
                ],
            }
        ],
        source_records=1,
        active_records=1,
        imported_records=1,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=10,
        warnings=[],
    )

    with pytest.raises(claude_to_codex.HandoffError, match="invalid base64"):
        claude_to_codex._native_import_records(plan, tmp_path / "assets")


def test_native_import_path_is_stable_and_inside_claude_projects(tmp_path):
    plan = claude_to_codex.HandoffPlan(
        source=claude_to_codex.SourceInfo(
            path="/tmp/source.jsonl",
            sha256="a" * 64,
            session_id="session-1",
            title="Task",
            cwd="/tmp",
            leaf_uuid="leaf",
            compact_boundary_uuid=None,
            first_imported_uuid="first",
            last_imported_uuid="last",
        ),
        items=[
            {
                "type": "message",
                "role": "user",
                "content": [{"type": "input_text", "text": "hi"}],
            }
        ],
        source_records=1,
        active_records=1,
        imported_records=1,
        hidden_reasoning_blocks_skipped=0,
        approximate_tokens=10,
        warnings=[],
    )

    first = claude_to_codex._native_import_path(plan, tmp_path)
    second = claude_to_codex._native_import_path(plan, tmp_path)

    assert first == second
    assert first.parent == tmp_path.resolve() / ".mem0-handoffs"
    assert first.suffix == ".jsonl"


def test_codex_context_limits_use_model_metadata_and_config(tmp_path):
    (tmp_path / "config.toml").write_text(
        'model = "gpt-5.6-sol"\n',
        encoding="utf-8",
    )
    (tmp_path / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "gpt-5.6-sol",
                        "context_window": 272_000,
                        "max_context_window": 872_000,
                        "effective_context_window_percent": 95,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    limits = claude_to_codex._codex_context_limits(tmp_path)

    assert limits.context_window == 272_000
    assert limits.usable_context_window == 258_400
    assert limits.auto_compact_token_limit == 244_800
    assert limits.max_context_window == 872_000
    assert limits.max_usable_context_window == 828_400
    assert limits.max_auto_compact_token_limit == 784_800


def test_codex_context_limits_honor_and_clamp_user_overrides(tmp_path):
    (tmp_path / "config.toml").write_text(
        "\n".join(
            [
                'model = "gpt-5.6-sol"',
                "model_context_window = 900000",
                "model_auto_compact_token_limit = 900000",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "gpt-5.6-sol",
                        "context_window": 272_000,
                        "max_context_window": 872_000,
                        "effective_context_window_percent": 95,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    limits = claude_to_codex._codex_context_limits(tmp_path)

    assert limits.context_window == 872_000
    assert limits.auto_compact_token_limit == 784_800


def test_compact_imported_thread_waits_for_native_compaction():
    class FakeServer:
        def __init__(self):
            self.requests = []
            self.notifications = iter(
                [
                    {
                        "method": "thread/tokenUsage/updated",
                        "params": {
                            "threadId": "thread-1",
                            "tokenUsage": {"total": {"totalTokens": 50_000}},
                        },
                    },
                    {
                        "method": "item/completed",
                        "params": {
                            "threadId": "thread-1",
                            "item": {"type": "contextCompaction", "id": "compact-1"},
                        },
                    },
                    {
                        "method": "turn/completed",
                        "params": {
                            "threadId": "thread-1",
                            "turn": {"status": "completed"},
                        },
                    },
                ]
            )

        def request(self, method, params, timeout):
            self.requests.append((method, params, timeout))
            return {}

        def wait_for_any_notification(self, methods, predicate, timeout):
            notification = next(self.notifications)
            assert notification["method"] in methods
            assert predicate(notification["params"])
            return notification

    server = FakeServer()

    usage = claude_to_codex._compact_imported_thread(server, "thread-1")

    assert [request[0] for request in server.requests] == [
        "thread/resume",
        "thread/compact/start",
    ]
    assert usage == {"total": {"totalTokens": 50_000}}


def test_set_thread_name_uses_claude_title():
    class FakeServer:
        def __init__(self):
            self.requests = []

        def request(self, method, params, timeout):
            self.requests.append((method, params, timeout))

    server = FakeServer()

    claude_to_codex._set_thread_name(server, "thread-1", "Memory Testing")

    assert server.requests == [
        (
            "thread/name/set",
            {"threadId": "thread-1", "name": "Memory Testing"},
            30,
        )
    ]


def test_command_output_is_short_and_names_the_created_task():
    rendered = claude_to_codex._command_output(
        {
            "thread_id": "thread-1",
            "title": "Memory Testing",
            "cwd": "/tmp/robotics",
            "compacted_before_return": True,
            "preview": "large imported message that must not be printed",
        }
    )

    assert rendered == (
        'Created Codex task "Memory Testing".\n'
        "Task ID: thread-1\n"
        "Project: robotics\n"
        "Codex compacted the transferred context before opening the task.\n"
        'Open Codex and select "Memory Testing" under robotics.'
    )
    assert "large imported message" not in rendered


def test_create_uses_selected_codex_home_and_native_import(tmp_path, monkeypatch):
    monkeypatch.setattr(claude_to_codex.Path, "home", lambda: tmp_path)
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "test-model"\n')
    (codex_home / "models_cache.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "slug": "test-model",
                        "context_window": 100000,
                        "max_context_window": 200000,
                    }
                ]
            }
        )
    )
    executable = tmp_path / "fake-codex"
    executable.write_text(
        f"#!{sys.executable}\n"
        + """
import json
import os
import sys
from pathlib import Path
home = Path(os.environ["CODEX_HOME"])
assert sys.argv[1:] == ["app-server", "--stdio"]
for line in sys.stdin:
    request = json.loads(line)
    method = request["method"]
    with (home / "requests.jsonl").open("a") as log:
        log.write(json.dumps(request) + "\\n")
    if "id" not in request:
        continue
    result = {}
    if method == "externalAgentConfig/import":
        source = request["params"]["migrationItems"][0]["details"]["sessions"][0]["path"]
        records = [json.loads(line) for line in Path(source).read_text().splitlines()]
        assert records[1]["message"]["content"] == "Continue here"
        result = {"importId": "import-1"}
    elif method == "thread/read":
        result = {"thread": {"turns": [{"id": "historical-turn"}], "preview": "Continue here"}}
    print(json.dumps({"id": request["id"], "result": result}), flush=True)
    if method == "externalAgentConfig/import":
        print(json.dumps({"method": "externalAgentConfig/import/completed", "params": {
            "importId": "import-1", "itemTypeResults": [{"itemType": "SESSIONS", "successes": [
                {"source": source, "target": "thread-1"}]}]}}), flush=True)
"""
    )
    executable.chmod(0o700)
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Continue here")])
    plan = claude_to_codex.build_plan(str(session), tmp_path)

    result = claude_to_codex.create_codex_thread(plan, str(executable), codex_home)

    assert result["thread_id"] == "thread-1"
    assert result["visible_turns"] == 1
    assert result["model_invoked"] is False
    requests = [json.loads(line) for line in (codex_home / "requests.jsonl").read_text().splitlines()]
    assert [item["method"] for item in requests] == [
        "initialize",
        "initialized",
        "externalAgentConfig/import",
        "thread/read",
        "thread/name/set",
    ]
    assert not (tmp_path / ".claude" / "projects" / ".mem0-handoffs").exists()
    imported_source = requests[2]["params"]["migrationItems"][0]["details"]["sessions"][0]["path"]
    assert Path(imported_source).parent == tmp_path / ".claude" / "projects" / ".mem0-handoffs"


def test_failed_import_saves_private_recovery_inside_handoff_directory(tmp_path, monkeypatch, capsys):
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Do not lose this", sessionId="../../escape")])
    monkeypatch.setattr(claude_to_codex, "DEFAULT_BUNDLE_DIR", tmp_path / "recovery")

    def fail(*args, **kwargs):
        raise claude_to_codex.HandoffError("Importer unavailable")

    monkeypatch.setattr(claude_to_codex, "create_codex_thread", fail)
    assert claude_to_codex.main(["--session", str(session), "--create"]) == 1
    (bundle,) = (tmp_path / "recovery").glob("*.json")
    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600
    assert "Do not lose this" in json.dumps(claude_to_codex.load_bundle(bundle).items)
    assert str(bundle) in capsys.readouterr().err


def test_initialization_failure_stops_app_server(tmp_path, monkeypatch):
    from unittest.mock import Mock

    process = Mock()
    process.stdout = []
    process.stderr = []
    process.poll.return_value = None
    monkeypatch.setattr(claude_to_codex.shutil, "which", lambda value: value)
    monkeypatch.setattr(claude_to_codex.subprocess, "Popen", lambda *args, **kwargs: process)

    def fail(*args, **kwargs):
        raise claude_to_codex.HandoffError("Unsupported importer")

    monkeypatch.setattr(claude_to_codex.CodexAppServer, "request", fail)
    with pytest.raises(claude_to_codex.HandoffError, match="Unsupported importer"):
        claude_to_codex.CodexAppServer(codex_home=tmp_path)
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)


def test_python_310_can_export_but_creation_explains_requirement(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "tomllib", None)
    with pytest.raises(claude_to_codex.HandoffError, match="Python 3.11"):
        claude_to_codex._codex_context_limits(tmp_path)
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Keep this")])
    assert claude_to_codex.main(["--session", str(session), "--export", str(tmp_path / "saved.json")]) == 0


def test_bundle_rejects_invalid_source_types(tmp_path):
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Keep this")])
    payload = claude_to_codex.build_plan(str(session), tmp_path).bundle()
    payload["source"]["session_id"] = ["invalid"]
    bundle = tmp_path / "invalid.json"
    bundle.write_text(json.dumps(payload))
    with pytest.raises(claude_to_codex.HandoffError, match="incomplete"):
        claude_to_codex.load_bundle(bundle)


@pytest.mark.parametrize("attachment_type", ["file", "image"])
def test_unsupported_visible_attachments_fail(attachment_type):
    with pytest.raises(claude_to_codex.HandoffError, match="unsupported payload"):
        claude_to_codex._attachment_item(
            {
                "uuid": "attachment",
                "attachment": {
                    "type": attachment_type,
                    "content": {"type": "unsupported"},
                },
            }
        )


def test_non_object_transcript_record_fails(tmp_path):
    session = tmp_path / "source.jsonl"
    session.write_text("[]\n")
    with pytest.raises(claude_to_codex.HandoffError, match="not an object"):
        claude_to_codex.build_plan(str(session), tmp_path)


def test_custom_claude_projects_directory_only_controls_source_lookup(tmp_path, monkeypatch):
    projects = tmp_path / "custom-projects"
    (projects / "fixture").mkdir(parents=True)
    session = projects / "fixture" / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Continue")])
    calls = []

    def create(plan, *, codex_bin, codex_home):
        calls.append(plan)
        return {"thread_id": "thread-1"}

    monkeypatch.setattr(claude_to_codex, "create_codex_thread", create)
    assert (
        claude_to_codex.main(
            [
                "--session",
                "source",
                "--claude-projects-dir",
                str(projects),
                "--create",
            ]
        )
        == 0
    )
    assert calls[0].source.path == str(session.resolve())


def test_native_import_failure_preserves_diagnostic(tmp_path, monkeypatch):
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Continue")])
    plan = claude_to_codex.build_plan(str(session), tmp_path)
    monkeypatch.setattr(claude_to_codex.Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        claude_to_codex,
        "_codex_context_limits",
        lambda home: claude_to_codex.CodexContextLimits(
            "test",
            10000,
            9500,
            9000,
            10000,
            9500,
            9000,
        ),
    )

    class Server:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, method, params, **kwargs):
            return {"importId": "import-1"}

        def wait_for_notification(self, *args):
            return {
                "params": {
                    "importId": "import-1",
                    "itemTypeResults": [
                        {
                            "itemType": "SESSIONS",
                            "failures": [{"error": "session_not_detected"}],
                        }
                    ],
                }
            }

    monkeypatch.setattr(claude_to_codex, "CodexAppServer", Server)
    with pytest.raises(claude_to_codex.HandoffError, match="session_not_detected"):
        claude_to_codex.create_codex_thread(plan, codex_home=tmp_path / "codex")
