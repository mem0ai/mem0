"""Native transcript readers producing complete, host-neutral handoff resources.

Formats: openai/codex rollout payloads; MoonshotAI/kimi-code contextMemory;
Pi's session-manager.buildSessionContext; native Cursor/Antigravity transcripts.
Unsupported state changes fail instead of silently dropping active context.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import handoff_engine as engine


def _message(role: str, text: str) -> dict:
    return {"role": role, "content": [{"type": "text", "text": text}]}


def _parts(content: Any, role: str, warnings: list[str]) -> list[dict]:
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        raise engine.HandoffError("Native message has invalid content.")
    parts = []
    for part in content:
        if not isinstance(part, dict):
            raise engine.HandoffError("Native message has an invalid content block.")
        kind = part.get("type")
        if kind in {"thinking", "redacted_thinking", "think"}:
            if "Hidden reasoning was excluded." not in warnings:
                warnings.append("Hidden reasoning was excluded.")
        elif kind in {"text", "input_text", "output_text"} and isinstance(part.get("text"), str):
            parts.append({"type": "input_text" if role == "user" else "output_text", "text": part["text"]})
        elif kind == "image":
            source = part.get("source") or {
                "type": "base64",
                "data": part.get("data"),
                "media_type": part.get("mimeType"),
            }
            media_type, data = engine._image_payload(source, "Native message image")
            parts.append({"type": "input_image", "image_url": f"data:{media_type};base64,{data}"})
        elif kind in {"image_url", "input_image"}:
            url = part.get("image_url")
            if isinstance(url, dict):
                url = url.get("url")
            engine._data_url_payload(url, "Native message image")
            parts.append({"type": "input_image", "image_url": url})
        elif kind not in {"toolCall", "tool_use"}:
            raise engine.HandoffError(f"Unsupported native content block: {kind!r}.")
    return parts


def _call_item(call: dict) -> dict:
    function = call.get("function", call)
    arguments = function.get("arguments", "{}")
    return {
        "type": "function_call",
        "call_id": call.get("id"),
        "name": function.get("name"),
        "arguments": arguments if isinstance(arguments, str) else json.dumps(arguments),
    }


def _messages_items(messages: list[dict], warnings: list[str]) -> list[dict]:
    items = []
    for message in messages:
        if not isinstance(message, dict):
            raise engine.HandoffError("Invalid native message.")
        role = message.get("role")
        if role in {"system", "developer"}:
            if "Source harness instructions were excluded." not in warnings:
                warnings.append("Source harness instructions were excluded.")
            continue
        if role in {"tool", "toolResult"}:
            output_parts = _parts(message.get("content"), "assistant", warnings)
            output = []
            for part in output_parts:
                if part["type"] == "input_image":
                    media_type, data = engine._data_url_payload(part["image_url"], "Tool result image")
                    output.append(
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": data}}
                    )
                else:
                    output.append({"type": "text", "text": part["text"]})
            if message.get("isError"):
                output.insert(0, {"type": "text", "text": "Tool failed."})
            if message.get("note"):
                output.append({"type": "text", "text": str(message["note"])})
            item = {
                "type": "function_call_output",
                "call_id": message.get("toolCallId") or message.get("tool_call_id"),
                "output": output,
            }
            if message.get("toolName") or message.get("name"):
                item["name"] = message.get("toolName") or message["name"]
            items.append(item)
            continue
        if role not in {"user", "assistant"}:
            raise engine.HandoffError(f"Unsupported native message role: {role!r}.")
        if message.get("partial") or message.get("stopReason") in {"error", "aborted"}:
            raise engine.HandoffError("Native assistant response is incomplete; finish the source turn first.")
        content = message.get("content", [])
        if isinstance(content, str):
            content = [{"type": "text", "text": content}]
        if not isinstance(content, list):
            raise engine.HandoffError("Native message has invalid content.")
        parts = []
        for part in content:
            if isinstance(part, dict) and part.get("type") in {"toolCall", "tool_use"}:
                if role != "assistant":
                    raise engine.HandoffError("Native user message contains an assistant tool call.")
                if parts:
                    items.append({"type": "message", "role": role, "content": parts})
                    parts = []
                items.append(
                    _call_item(
                        {
                            "id": part.get("id"),
                            "name": part.get("name"),
                            "arguments": json.dumps(part.get("arguments", part.get("input", {}))),
                        }
                    )
                )
            else:
                parts.extend(_parts([part], role, warnings))
        if parts:
            items.append({"type": "message", "role": role, "content": parts})
        for call in message.get("toolCalls") or message.get("tool_calls") or []:
            items.append(_call_item(call))
    return items


def _codex(records: list[dict], warnings: list[str]) -> tuple[list[dict], dict]:
    # Native Responses items are the authoritative history, event_msg is UI data.
    items, source = [], {}
    for record in records:
        kind, payload = record.get("type"), record.get("payload")
        if not isinstance(payload, dict):
            raise engine.HandoffError("Invalid Codex rollout payload.")
        if kind == "session_meta":
            source.update(session_id=payload.get("id"), cwd=payload.get("cwd"))
        elif kind == "compacted":
            replacement = payload.get("replacement_history")
            if not isinstance(replacement, list) or not replacement:
                raise engine.HandoffError(
                    "Codex compaction is opaque; a complete plaintext replacement history is required."
                )
            items = list(replacement)
        elif kind == "response_item":
            items.append(payload)
        elif kind == "event_msg":
            if payload.get("type") == "thread_rolled_back":
                raise engine.HandoffError("Codex rollback requires a native active-context export.")
        # Codex 0.153+ persists harness snapshots and accounting beside response_items.
        # These records are not conversation history and must not become user context.
        elif kind not in {"turn_context", "world_state", "token_usage_record"}:
            raise engine.HandoffError(f"Unsupported Codex rollout record: {kind!r}.")
    result = []
    for item in items:
        kind = item.get("type")
        if kind == "reasoning":
            warnings.append("Hidden reasoning was excluded.")
        elif kind == "message" and item.get("role") in {"system", "developer"}:
            warnings.append("Source harness instructions were excluded.")
        elif kind == "custom_tool_call":
            result.append(
                {
                    "type": "function_call",
                    "call_id": item.get("call_id"),
                    "name": item.get("name"),
                    "arguments": json.dumps({"input": item.get("input")}),
                }
            )
        elif kind == "custom_tool_call_output":
            result.append({**item, "type": "function_call_output"})
        elif kind == "compaction":
            raise engine.HandoffError(
                "Codex compaction contains opaque model state; it cannot be transferred losslessly."
            )
        else:
            result.append(dict(item))
    return result, source


def _cursor(records: list[dict], warnings: list[str]) -> tuple[list[dict], dict]:
    # Cursor's persisted transcript uses role + message.content, without Claude's parent chain.
    converted = []
    source = {}
    for index, record in enumerate(records):
        role = record.get("role") or record.get("type")
        if role not in {"user", "assistant"} or not isinstance(record.get("message"), dict):
            raise engine.HandoffError("Unsupported Cursor transcript record; provide a complete native JSONL export.")
        converted.append({**record, "type": role, "uuid": str(index)})
        if record.get("session_id"):
            source["session_id"] = record["session_id"]
        if record.get("cwd"):
            source["cwd"] = record["cwd"]
    items, skipped = engine._responses_items(converted)
    if skipped:
        warnings.append("Hidden reasoning was excluded.")
    return items, source


def _antigravity(records: list[dict], warnings: list[str]) -> tuple[list[dict], dict]:
    messages = []
    for step in records:
        if step.get("status") != "DONE":
            raise engine.HandoffError("Antigravity has an unfinished transcript step; finish the source turn first.")
        kind, content = step.get("type"), step.get("content")
        if not isinstance(content, str):
            raise engine.HandoffError("Antigravity transcript content is not transferable text.")
        if kind == "USER_INPUT":
            messages.append(_message("user", content))
        elif kind == "PLANNER_RESPONSE" and step.get("source") == "MODEL":
            messages.append(_message("assistant", content))
        else:
            raise engine.HandoffError(
                f"Unsupported Antigravity step {kind!r}; its visible conversation semantics are not verified."
            )
    return _messages_items(messages, warnings), {}


def _kimi_compact(messages: list[dict], record: dict) -> list[dict]:
    summary = record.get("contextSummary", record.get("summary"))
    if isinstance(summary, dict):
        summary_message = summary
    elif isinstance(summary, str):
        summary_message = {**_message("user", summary), "origin": {"kind": "compaction_summary"}}
    else:
        raise engine.HandoffError("Kimi compaction has no transferable summary.")
    if record.get("legacyTail") or "keptUserMessageCount" not in record:
        count = record.get("compactedCount", record.get("count"))
        if not isinstance(count, int) or not 0 <= count <= len(messages):
            raise engine.HandoffError("Invalid Kimi compaction boundary.")
        return [summary_message, *messages[count:]]
    users = []
    for message in messages:
        origin = message.get("origin") or {}
        if message.get("role") == "user" and (
            origin.get("kind") in {None, "user"}
            or (origin.get("kind") in {"skill_activation", "plugin_command"} and origin.get("trigger") == "user-slash")
        ):
            users.append(message)
    # Kimi trims user inputs above this native budget. Do not approximate that destructive rewrite.
    tokens = 0
    for message in users:
        if message.get("toolCalls"):
            raise engine.HandoffError("Unsupported Kimi compaction user tool calls.")
        tokens += 1  # estimateTokens('user')
        for part in message.get("content", []):
            if part.get("type") not in {"text", "think"}:
                tokens += 2000
            else:
                text = part.get("text", part.get("think", ""))
                ascii_count = sum(ord(char) <= 127 for char in text)
                tokens += (ascii_count + 3) // 4 + len(text) - ascii_count
    if tokens > 20000 or record.get("keptHeadUserMessageCount"):
        raise engine.HandoffError("Kimi compaction elided user content; use a native active-context bundle export.")
    continuation = _message(
        "user",
        "<system-reminder>\nContext compaction is complete — continue the work that was in progress when it began.\n</system-reminder>",
    )
    continuation["origin"] = {"kind": "injection", "variant": "compaction_continuation"}
    return [*users, summary_message, continuation]


def _kimi(records: list[dict], warnings: list[str]) -> tuple[list[dict], dict]:
    # Mirrors Kimi v2 context.append_message and completed loop events, not UI stream fragments.
    messages, source = [], {}
    opened, step_id = None, None
    for record in records:
        if record.get("agentId") not in {None, "main"}:
            continue
        kind = record.get("type", "")
        if kind in {"profile.bind", "config.update"}:
            cwd = (record.get("environmentDisclosure") or {}).get("cwd") or record.get("cwd")
            if cwd:
                source["cwd"] = cwd
        elif kind == "context.append_message":
            if opened is not None:
                raise engine.HandoffError("Kimi interleaved messages require a completed native context export.")
            messages.append(record.get("message"))
        elif kind == "context.append_loop_event":
            event = record.get("event") or {}
            event_type = event.get("type")
            if event_type == "step.begin":
                if opened is not None:
                    raise engine.HandoffError("Kimi previous response did not complete.")
                step_id = event.get("uuid")
                opened = {"role": "assistant", "content": [], "toolCalls": []}
                messages.append(opened)
            elif event_type == "step.end":
                if event.get("uuid") != step_id or event.get("finishReason") in {"error", "interrupted"}:
                    raise engine.HandoffError("Kimi response is incomplete or interrupted.")
                opened, step_id = None, None
            elif event_type in {"content.part", "tool.call"}:
                if opened is None or event.get("stepUuid") != step_id:
                    raise engine.HandoffError("Kimi content has no matching active response.")
                if event_type == "content.part":
                    opened["content"].append(event.get("part"))
                else:
                    opened["toolCalls"].append(
                        {
                            "id": event.get("toolCallId"),
                            "name": event.get("name"),
                            "arguments": json.dumps(event.get("args", {})),
                        }
                    )
            elif event_type == "tool.result":
                result = event.get("result") or {}
                messages.append(
                    {
                        "role": "tool",
                        "toolCallId": event.get("toolCallId"),
                        "content": result.get("output"),
                        "isError": result.get("isError"),
                        "note": result.get("note"),
                    }
                )
            else:
                raise engine.HandoffError(f"Unsupported Kimi loop event: {event_type!r}.")
        elif kind == "context.clear":
            messages, opened, step_id = [], None, None
        elif kind == "context.apply_compaction":
            if opened is not None:
                raise engine.HandoffError("Kimi compaction began during an unfinished response.")
            messages = _kimi_compact(messages, record)
        elif kind in {"context.undo", "micro_compaction.apply", "context.spliced"}:
            raise engine.HandoffError(f"Kimi {kind} needs a native active-context export to preserve its state.")
        elif kind.startswith("context.") and kind != "context.update_token_count":
            raise engine.HandoffError(f"Unsupported Kimi context event: {kind!r}.")
        # Remaining durable events configure Kimi's harness; they are not model messages.
    if opened is not None:
        raise engine.HandoffError("Kimi response is still streaming.")
    return _messages_items(messages, warnings), source


def _pi(records: list[dict], warnings: list[str]) -> tuple[list[dict], dict]:
    header = records[0]
    if header.get("type") != "session":
        raise engine.HandoffError("Pi/OpenClaw transcript has no session header.")
    entries = [record for record in records[1:] if isinstance(record.get("id"), str)]
    if len(entries) != len(records) - 1:
        raise engine.HandoffError("Pi/OpenClaw transcript entry has no ID.")
    index = {entry["id"]: entry for entry in entries}
    if len(index) != len(entries):
        raise engine.HandoffError("Pi/OpenClaw transcript has duplicate entry IDs.")
    chain, seen = [], set()
    current = entries[-1] if entries else None
    while current:
        if current["id"] in seen:
            raise engine.HandoffError("Pi/OpenClaw transcript has a parent cycle.")
        seen.add(current["id"])
        chain.append(current)
        parent = current.get("parentId")
        if parent is not None and parent not in index:
            raise engine.HandoffError("Pi/OpenClaw transcript has a missing parent.")
        current = index.get(parent)
    chain.reverse()
    # Pi's getSessionName is session-wide, even when the latest rename is on another branch.
    title = next((entry.get("name") for entry in reversed(entries) if entry.get("type") == "session_info"), None)
    messages = []
    boundary = next((i for i in range(len(chain) - 1, -1, -1) if chain[i].get("type") == "compaction"), None)
    if boundary is not None:
        compact = chain[boundary]
        if not isinstance(compact.get("summary"), str):
            raise engine.HandoffError("Pi/OpenClaw compaction has no summary.")
        messages.append(
            _message(
                "user",
                f"The conversation history before this point was compacted into the following summary:\n\n<summary>\n{compact['summary']}\n</summary>",
            )
        )
        kept = next((i for i in range(boundary) if chain[i]["id"] == compact.get("firstKeptEntryId")), boundary)
        chain = chain[kept:boundary] + chain[boundary + 1 :]
    for entry in chain:
        kind = entry.get("type")
        if kind == "message":
            message = entry.get("message")
            if not isinstance(message, dict):
                raise engine.HandoffError("Invalid Pi/OpenClaw message.")
            if message.get("role") == "bashExecution":
                if message.get("excludeFromContext"):
                    continue
                if message.get("truncated"):
                    raise engine.HandoffError("Pi/OpenClaw shell output is truncated; provide a complete bundle.")
                text = f"Ran `{message.get('command', '')}`\n"
                text += f"```\n{message['output']}\n```" if message.get("output") else "(no output)"
                if message.get("cancelled"):
                    text += "\n\n(command cancelled)"
                elif message.get("exitCode") not in {None, 0}:
                    text += f"\n\nCommand exited with code {message['exitCode']}"
                message = _message("user", text)
            messages.append(message)
        elif kind == "branch_summary":
            messages.append(
                _message(
                    "user",
                    f"The following is a summary of a branch that this conversation came back from:\n\n<summary>\n{entry['summary']}</summary>",
                )
            )
        elif kind == "custom_message":
            messages.append({"role": "user", "content": entry.get("content")})
        elif kind not in {"model_change", "thinking_level_change", "custom", "label", "session_info"}:
            raise engine.HandoffError(f"Unsupported Pi/OpenClaw entry: {kind!r}.")
    return _messages_items(messages, warnings), {
        "session_id": header.get("id"),
        "cwd": header.get("cwd"),
        "title": title,
    }


def read_source(host: str, path: Path, *, cwd: Path | None = None, title: str | None = None) -> engine.HandoffPlan:
    path = path.expanduser().resolve()
    records, digest = engine._stable_jsonl(path)
    warnings: list[str] = []
    readers = {
        "cursor": _cursor,
        "codex": _codex,
        "kimi": _kimi,
        "antigravity": _antigravity,
        "openclaw": _pi,
        "pi-agent": _pi,
    }
    try:
        items, metadata = readers[host](records, warnings)
    except (TypeError, AttributeError, KeyError, ValueError) as exc:
        raise engine.HandoffError(f"Invalid {host} native transcript structure: {exc}") from exc
    if host == "kimi" and path.name == "wire.jsonl" and path.parent.name == "main":
        metadata.setdefault("session_id", path.parents[2].name)
        state = path.parents[2] / "state.json"
        if state.is_file():
            try:
                metadata.setdefault("title", json.loads(state.read_text()).get("title"))
            except (json.JSONDecodeError, AttributeError):
                pass
    if host == "antigravity" and path.name == "transcript.jsonl" and path.parent.name == "logs":
        metadata.setdefault("session_id", path.parents[2].name)
    source_cwd = str(cwd.expanduser().resolve()) if cwd else metadata.get("cwd")
    if not source_cwd:
        raise engine.HandoffError(f"{host} transcript has no working directory; provide --cwd.")
    source = {
        "host": host,
        "path": str(path),
        "sha256": digest,
        "session_id": metadata.get("session_id") or path.stem,
        "cwd": source_cwd,
        "title": title or metadata.get("title") or f"{host} session {path.stem[:12]}",
    }
    return engine.plan_from_bundle(
        {"format": engine.FORMAT_VERSION, "source": source, "items": items, "warnings": list(dict.fromkeys(warnings))}
    )
