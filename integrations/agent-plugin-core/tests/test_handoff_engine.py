from __future__ import annotations

import io
import json
import stat
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "python"


sys.path.insert(0, str(SCRIPTS))


import handoff_engine  # noqa: E402


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

    plan = handoff_engine.build_plan(str(session), tmp_path)

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

    plan = handoff_engine.build_plan(str(session), tmp_path)

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

    plan = handoff_engine.build_plan(str(session), tmp_path)

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

    plan = handoff_engine.build_plan(str(session), tmp_path)
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

    with pytest.raises(handoff_engine.HandoffError, match="unfinished tool call"):
        handoff_engine.build_plan(str(session), tmp_path)


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

    plan = handoff_engine.build_plan(str(session), tmp_path)

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

    with pytest.raises(handoff_engine.HandoffError, match="no matching call"):
        handoff_engine.build_plan(str(session), tmp_path)


def test_partial_jsonl_fails(tmp_path):
    session = tmp_path / "session-1.jsonl"
    session.write_text('{"type":"user"}', encoding="utf-8")

    with pytest.raises(handoff_engine.HandoffError, match="incomplete"):
        handoff_engine.build_plan(str(session), tmp_path)


def test_bundle_is_private(tmp_path):
    session = tmp_path / "session-1.jsonl"
    _write(
        session,
        [
            _record("u1", None, "user", content="Question"),
            _record("a1", "u1", "assistant", content=[{"type": "text", "text": "Answer"}]),
        ],
    )
    plan = handoff_engine.build_plan(str(session), tmp_path)
    bundle = handoff_engine.write_bundle(plan, tmp_path / "private" / "handoff.json")

    assert stat.S_IMODE(bundle.stat().st_mode) == 0o600
    assert json.loads(bundle.read_text())["format"] == handoff_engine.FORMAT_VERSION

    restored = handoff_engine.load_bundle(bundle)
    assert restored.source == plan.source
    assert restored.items == plan.items
    assert restored.approximate_tokens == plan.approximate_tokens


def test_explicit_cwd_can_relocate_a_session(tmp_path):
    plan = handoff_engine.HandoffPlan(
        source=handoff_engine.SourceInfo(
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

    relocated = handoff_engine._with_cwd(plan, tmp_path)

    assert relocated.source.cwd == "/path/that/no/longer/exists"
    assert relocated.source.project_cwd == str(tmp_path.resolve())


def test_bundle_rejects_invalid_source_types(tmp_path):
    session = tmp_path / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Keep this")])
    payload = handoff_engine.build_plan(str(session), tmp_path).bundle()
    payload["source"]["session_id"] = ["invalid"]
    bundle = tmp_path / "invalid.json"
    bundle.write_text(json.dumps(payload))
    with pytest.raises(handoff_engine.HandoffError, match="incomplete"):
        handoff_engine.load_bundle(bundle)


@pytest.mark.parametrize("attachment_type", ["file", "image"])
def test_unsupported_visible_attachments_fail(attachment_type):
    with pytest.raises(handoff_engine.HandoffError, match="unsupported payload"):
        handoff_engine._attachment_item(
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
    with pytest.raises(handoff_engine.HandoffError, match="not an object"):
        handoff_engine.build_plan(str(session), tmp_path)


@pytest.fixture
def resources(tmp_path, monkeypatch):
    monkeypatch.setattr(handoff_engine, "DEFAULT_BUNDLE_DIR", tmp_path / "handoffs")
    return tmp_path / "handoffs"


def _neutral(cwd, host="pi-agent"):
    return {
        "format": handoff_engine.FORMAT_VERSION,
        "source": {"host": host, "session_id": "session", "cwd": str(cwd), "title": "Full task context"},
        "items": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Continue"}]},
            {"type": "function_call", "call_id": "read1", "name": "Read", "arguments": '{"path":"file"}'},
            {"type": "function_call_output", "call_id": "read1", "name": "Read", "output": "evidence\n" * 100_000},
            {"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": "Last answer"}]},
        ],
        "warnings": ["Native readable compaction retained"],
    }


def test_cross_host_save_and_resume_preserves_complete_history_and_images(tmp_path, resources, monkeypatch, capsys):
    source = _neutral(tmp_path)
    image = {"type": "input_image", "image_url": "data:image/png;base64,aW1hZ2U="}
    source["items"][0]["content"].append(image)
    source["items"][2]["output"] = [
        {"type": "text", "text": "before\n" * 100_000},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "aW1hZ2U="}},
        {"type": "text", "text": "after"},
    ]
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(source)))
    assert handoff_engine.main(["--save", "--bundle", "-"]) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["source_host"] == "pi-agent"
    # A different plugin invokes the same resource API. No target app is required.
    assert handoff_engine.main(["--resume", saved["resource"], "--cwd", str(tmp_path), "--command-output"]) == 0
    resumed = json.loads(capsys.readouterr().out)
    assert resumed["context_type"] == "historical_session"
    assert resumed["handoff"]["source"]["host"] == "pi-agent"
    assert resumed["handoff"]["items"] == source["items"]
    assert resumed["handoff"]["warnings"] == source["warnings"]
    assert resumed["handoff"]["counts"]["responses_items"] == len(source["items"])
    assert list(resources.iterdir()) == [Path(saved["resource"])]


def test_resources_are_unique_private_and_never_overwritten(tmp_path, resources):
    plan = handoff_engine.plan_from_bundle(_neutral(tmp_path))
    first = handoff_engine.save_resource(plan)
    before = first.read_bytes()
    second = handoff_engine.save_resource(plan)
    assert first != second
    assert first.read_bytes() == second.read_bytes() == before
    assert stat.S_IMODE(resources.stat().st_mode) == 0o700
    assert stat.S_IMODE(first.stat().st_mode) == stat.S_IMODE(second.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        handoff_engine.write_bundle(plan, first)
    assert first.read_bytes() == before
    assert set(resources.iterdir()) == {first, second}


def test_list_scopes_to_repo_but_explicit_resume_allows_relocation(tmp_path, resources, monkeypatch):
    first, second = tmp_path / "project-one", tmp_path / "project-two"
    first.mkdir()
    second.mkdir()
    nested = first / "nested"
    nested.mkdir()
    monkeypatch.setattr(handoff_engine, "_git_root", lambda cwd: str(first) if cwd in (first, nested) else None)
    resource_a = handoff_engine.save_resource(handoff_engine.plan_from_bundle(_neutral(nested)))
    resource_b = handoff_engine.save_resource(handoff_engine.plan_from_bundle(_neutral(second, "opencode")))
    assert [item["resource"] for item in handoff_engine.list_resources(first)] == [str(resource_a)]
    assert [item["resource"] for item in handoff_engine.list_resources(nested)] == [str(resource_a)]
    assert [item["resource"] for item in handoff_engine.list_resources(second)] == [str(resource_b)]
    resumed = handoff_engine.resume_resource(resource_a, second)
    assert resumed["project_cwd"] == str(second)
    assert resumed["handoff"]["source"]["cwd"] == str(nested)
    assert resumed["handoff"]["source"]["project_cwd"] == str(first)


@pytest.mark.parametrize("damage", ["json", "unfinished", "unsupported", "missing"])
def test_invalid_resource_fails_without_executing_history(tmp_path, resources, monkeypatch, capsys, damage):
    resource = tmp_path / "invalid.json"
    payload = _neutral(tmp_path)
    if damage == "unfinished":
        payload["items"].pop(2)
    elif damage == "unsupported":
        payload["items"][0]["content"].append({"type": "executable", "command": "do not execute"})
    if damage != "missing":
        resource.write_text("{broken" if damage == "json" else json.dumps(payload))
    # Git repository detection is the only subprocess allowed; even that is unnecessary here.
    monkeypatch.setattr(handoff_engine, "_git_root", lambda cwd: None)
    monkeypatch.setattr(handoff_engine.subprocess, "run", lambda *a, **k: pytest.fail("unexpected process"))
    assert handoff_engine.main(["--resume", str(resource), "--cwd", str(tmp_path)]) == 1
    output = capsys.readouterr()
    assert "Handoff failed:" in output.err
    assert not output.out
    assert not resources.exists()


def test_failed_save_never_publishes_partial_resource(tmp_path, resources, monkeypatch, capsys):
    payload = _neutral(tmp_path)
    payload["items"].pop(2)
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))
    assert handoff_engine.main(["--save", "--bundle", "-"]) == 1
    assert "unfinished tool calls" in capsys.readouterr().err
    assert not resources.exists()


def test_list_reports_corrupt_resource_without_silently_omitting_it(tmp_path, resources):
    resources.mkdir()
    broken = resources / "broken.json"
    broken.write_text("[]")
    with pytest.raises(handoff_engine.HandoffError, match="broken.json"):
        handoff_engine.list_resources(tmp_path)


def test_legacy_bundle_project_cwd_migrates_without_changing_history(tmp_path):
    payload = _neutral(tmp_path, "claude-code")
    payload["format"] = "memo.claude-to-codex.v1"
    payload["source"]["codex_cwd"] = str(tmp_path)
    payload["source"].pop("host")
    plan = handoff_engine.plan_from_bundle(payload)
    assert plan.source.project_cwd == str(tmp_path)
    assert plan.source.host == "claude-code"
    assert "codex_cwd" not in plan.bundle()["source"]
    assert plan.items == payload["items"]


def test_claude_session_id_can_save_current_active_context(tmp_path, resources, capsys):
    projects = tmp_path / "claude-projects"
    project = projects / "fixture"
    project.mkdir(parents=True)
    session = project / "source.jsonl"
    _write(session, [_record("u1", None, "user", content="Continue", cwd=str(tmp_path))])
    assert (
        handoff_engine.main(
            [
                "--save",
                "--source",
                "claude-code",
                "--session",
                "source",
                "--claude-projects-dir",
                str(projects),
                "--command-output",
            ]
        )
        == 0
    )
    output = capsys.readouterr().out
    resource = next(resources.glob("*.json"))
    assert str(resource) in output
    assert handoff_engine.load_bundle(resource).source.path == str(session.resolve())
    assert handoff_engine.main(["--list", "--cwd", str(tmp_path), "--command-output"]) == 0
    assert str(resource) in capsys.readouterr().out


@pytest.mark.parametrize(
    "output",
    [
        {"type": "image", "source": {"type": "url", "url": "https://example.invalid/private"}},
        [{"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "broken"}}],
    ],
)
def test_invalid_tool_result_images_cannot_be_saved(tmp_path, resources, output):
    payload = _neutral(tmp_path)
    payload["items"][2]["output"] = output
    with pytest.raises(handoff_engine.HandoffError):
        handoff_engine.plan_from_bundle(payload)
    assert not resources.exists()


def test_save_and_resume_work_when_git_is_not_installed(tmp_path, resources, monkeypatch):
    def unavailable(*args, **kwargs):
        assert args[0][0] == "git"
        raise FileNotFoundError("git not installed")

    monkeypatch.setattr(handoff_engine.subprocess, "run", unavailable)
    plan = handoff_engine.plan_from_bundle(_neutral(tmp_path, "deepseek"))
    resource = handoff_engine.save_resource(plan)
    assert handoff_engine.resume_resource(resource, tmp_path)["handoff"]["items"] == plan.items
    assert handoff_engine.list_resources(tmp_path)[0]["resource"] == str(resource)


@pytest.mark.parametrize("invalid", [{"counts": {"source_records": -1}}, {"warnings": [None]}])
def test_invalid_resource_metadata_is_rejected(tmp_path, invalid):
    payload = _neutral(tmp_path)
    payload.update(invalid)
    with pytest.raises(handoff_engine.HandoffError):
        handoff_engine.plan_from_bundle(payload)
