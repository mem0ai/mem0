#!/usr/bin/env python3
"""Translate Kimi Code hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import configure_harness, record_sidekick_start, record_sidekick_stop, record_tool  # noqa: E402

EVENTS = {
    "SessionStart": ["session-start"],
    "UserPromptSubmit": ["user-prompt"],
    "PostToolUse": ["post-tool"],
    "PostToolUseFailure": ["post-tool-failure"],
    "Stop": ["stop"],
    "PreCompact": ["flush", "--reason", "pre-compact"],
    "SessionEnd": ["flush", "--reason", "session-end"],
    "SubagentStart": ["sidekick-start"],
    "SubagentStop": ["sidekick-stop"],
}


def _session_dir(session_id: str) -> Path | None:
    home = Path(os.environ.get("KIMI_CODE_HOME", Path.home() / ".kimi-code")).expanduser()
    found = None
    try:
        with (home / "session_index.jsonl").open(encoding="utf-8") as index:
            for line in index:
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if entry.get("sessionId") == session_id and isinstance(entry.get("sessionDir"), str):
                    found = Path(entry["sessionDir"])
    except OSError:
        pass
    if found:
        return found
    if not session_id or Path(session_id).name != session_id:
        return None
    return next((path for path in (home / "sessions").glob(f"*/{session_id}") if path.is_dir()), None)


def _last_assistant_message(transcript: Path) -> str:
    message = ""
    step_id = None
    parts = []
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("type") != "context.append_loop_event" or not isinstance(record.get("event"), dict):
            continue
        event = record["event"]
        if event.get("type") == "step.begin":
            step_id = event.get("uuid")
            parts = []
        elif event.get("type") == "content.part" and event.get("stepUuid") == step_id:
            part = event.get("part")
            if isinstance(part, dict) and part.get("type") == "text" and isinstance(part.get("text"), str):
                parts.append(part["text"])
        elif event.get("type") == "step.end" and event.get("uuid") == step_id:
            if event.get("finishReason") not in {"error", "interrupted"} and parts:
                message = "".join(parts)
            step_id = None
            parts = []
    return message


def normalize(payload: dict) -> dict:
    value = dict(payload)
    if "tool_output" in value:
        value.setdefault("tool_response", value["tool_output"])
    if "error" in value:
        value.setdefault("tool_response", value["error"])
    if "response" in value:
        value.setdefault("last_assistant_message", value["response"])
    if "agent_name" in value:
        value.setdefault("agent_type", value["agent_name"])
    if value.get("hook_event_name") == "Stop":
        session = _session_dir(str(value.get("session_id") or ""))
        transcript = session / "agents" / "main" / "wire.jsonl" if session else None
        if transcript and transcript.is_file():
            value.setdefault("transcript_path", str(transcript))
            if message := _last_assistant_message(transcript):
                value.setdefault("last_assistant_message", message)
    return value


def _sidekick_start(store, payload):
    payload = dict(payload)
    payload.setdefault("agent_id", f"kimi-{uuid.uuid4().hex}")
    context = record_sidekick_start(store, payload)
    return {"hookSpecificOutput": {"additionalContext": context}} if context else None


def _sidekick_stop(store, payload):
    record_sidekick_stop(store, payload)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in EVENTS:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    sys.argv = [sys.argv[0], *EVENTS[event]]
    sys.stdin = io.StringIO(json.dumps(normalize(raw if isinstance(raw, dict) else {})))
    configure_harness("kimi", data_dir_name="kimi-plugin", source_tag="kimi_plugin")
    telemetry.init(harness="kimi", source_tag="KIMI_PLUGIN")
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = hook_runner.run(
            extra_actions={
                "post-tool-failure": lambda store, payload: record_tool(store, payload, failed=True),
                "sidekick-start": _sidekick_start,
                "sidekick-stop": _sidekick_stop,
            },
            automatic_flush_reasons={"session-end", "pre-compact"},
        )
    if event in {"UserPromptSubmit", "SubagentStart"} and (raw_output := output.getvalue().strip()):
        parsed = json.loads(raw_output)
        context = parsed.get("hookSpecificOutput", {}).get("additionalContext", "")
        if context:
            print(context)
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        raise SystemExit(0) from None
