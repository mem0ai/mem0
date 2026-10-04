#!/usr/bin/env python3
"""Translate Antigravity hooks into the shared Mem0 runtime."""

from __future__ import annotations

import contextlib
import io
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
BUNDLED_CORE = HERE.parent.parent / "core"
CORE = BUNDLED_CORE if BUNDLED_CORE.is_dir() else HERE.parents[2] / "core" / "python"
sys.path.insert(0, str(CORE))

import hook_runner  # noqa: E402
import telemetry  # noqa: E402
from memory_core import (  # noqa: E402
    configure_harness,
    record_tool,
    redact,
)


def _read_transcript(path: str) -> list[dict[str, str]]:
    messages = []
    try:
        with open(path, encoding="utf-8") as transcript:
            for line in transcript:
                try:
                    step = json.loads(line)
                except json.JSONDecodeError:
                    continue
                content = step.get("content")
                if not isinstance(content, str) or step.get("status") != "DONE":
                    continue
                if step.get("type") == "USER_INPUT":
                    match = re.search(r"<USER_REQUEST>\s*(.*?)\s*</USER_REQUEST>", content, re.DOTALL)
                    messages.append({"role": "user", "content": redact(match.group(1) if match else content).strip()})
                elif step.get("source") == "MODEL" and step.get("type") == "PLANNER_RESPONSE":
                    messages.append({"role": "assistant", "content": redact(content).strip()})
    except (OSError, TypeError):
        pass
    return messages


def _transcript_messages(path: str) -> tuple[str, str]:
    messages = _read_transcript(path)
    return tuple(next((m["content"] for m in reversed(messages) if m["role"] == role), "")
                 for role in ("user", "assistant"))


def _record_stop(store, payload):
    session_id = str(payload.get("session_id") or "unknown-session")
    repo = store.repo_for_session(session_id, payload.get("cwd"))
    path = str(payload.get("transcript_path") or "")
    messages = _read_transcript(path)
    if not messages:
        return hook_runner.default_record_stop(store, payload)
    with store.conn:
        store.conn.execute("BEGIN IMMEDIATE")
        previous = store.latest_event_payload(repo.identity, session_id, "assistant_stop")
        offset = previous.get("transcript_count", 0) if previous.get("transcript_path") == path else 0
        if not isinstance(offset, int) or not 0 <= offset <= len(messages):
            offset = 0
        if messages[offset:]:
            store.record_event(repo, session_id, "assistant_stop", {
                "transcript_messages": messages[offset:],
                "transcript_count": len(messages),
                "transcript_path": path,
            })
    return repo, session_id


def normalize(payload: dict) -> dict:
    value = dict(payload)
    value.setdefault("session_id", value.get("conversationId", ""))
    workspaces = value.get("workspacePaths") or []
    cwd = workspaces[0] if workspaces else os.environ.get("MEM0_CWD", "").strip()
    if cwd:
        value.setdefault("cwd", cwd)
    value.setdefault("transcript_path", value.get("transcriptPath", ""))
    prompt, assistant = _transcript_messages(value["transcript_path"])
    if prompt:
        value.setdefault("prompt", prompt)
    if assistant:
        value.setdefault("last_assistant_message", assistant)
    tool_call = value.get("toolCall") or {}
    if isinstance(tool_call, dict):
        value.setdefault("tool_name", tool_call.get("name", ""))
        value.setdefault("tool_input", tool_call.get("args", {}))
    if value.get("error"):
        value.setdefault("tool_response", value["error"])
    return value


def _record_failure(store, payload):
    return record_tool(store, payload, failed=True)


def _run_shared(arguments: list[str], payload: dict) -> tuple[int, str]:
    sys.argv = [sys.argv[0], *arguments]
    sys.stdin = io.StringIO(json.dumps(payload))
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        result = hook_runner.run(
            record_stop_fn=_record_stop,
            extra_actions={"post-tool-failure": _record_failure},
            automatic_flush_reasons={"session-end"},
        )
    return result, output.getvalue()


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"PreInvocation", "PostToolUse", "Stop"}:
        return 2
    event = sys.argv[1]
    try:
        raw = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        raw = {}
    payload = normalize(raw if isinstance(raw, dict) else {})
    if not payload.get("cwd"):
        output = {"injectSteps": []} if event == "PreInvocation" else {}
        if event == "Stop":
            output = {"decision": "allow"}
        print(json.dumps(output))
        return 0
    configure_harness("antigravity", data_dir_name="antigravity-plugin", source_tag="antigravity_plugin")
    telemetry.init(harness="antigravity", source_tag="ANTIGRAVITY_PLUGIN")
    if event == "PreInvocation":
        if payload.get("invocationNum") != 0:
            print(json.dumps({"injectSteps": []}))
            return 0
        _run_shared(["session-start"], payload)
        result, output = _run_shared(["user-prompt"], payload)
        context = ""
        for line in output.splitlines():
            try:
                context = json.loads(line)["hookSpecificOutput"]["additionalContext"]
            except (json.JSONDecodeError, KeyError, TypeError):
                continue
        print(json.dumps({"injectSteps": [{"ephemeralMessage": context}] if context else []}))
        return result
    action = {
        "PostToolUse": ["post-tool-failure" if payload.get("error") else "post-tool"],
        "Stop": ["flush", "--reason", "session-end"],
    }[event]
    result, _ = _run_shared(action, payload)
    print(json.dumps({"decision": "allow"} if event == "Stop" else {}))
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        hook_runner.log_failure(exc)
        print("{}")
        raise SystemExit(0) from None
