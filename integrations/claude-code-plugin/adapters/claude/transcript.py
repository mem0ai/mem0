"""Claude Code transcript parsing for Mem0 memory extraction."""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

import sys

_here = Path(__file__).resolve()
sys.path.insert(0, str(_here.parents[2] / "core" / "python"))

from memory_core import (  # noqa: E402
    EvidenceStore,
    RepoContext,
    MAX_ASSISTANT_CHARS,
    _session_id,
    bounded,
    redact,
)


def _message_content_text(content: Any) -> str:
    """Return visible text from one Claude transcript message."""
    if isinstance(content, str):
        return redact(content).strip()
    if not isinstance(content, list):
        return ""
    parts = []
    for block in content:
        if not isinstance(block, dict) or block.get("type") != "text":
            continue
        text = redact(block.get("text", "")).strip()
        if text:
            parts.append(text)
    return "\n\n".join(parts)


def _transcript_rows(
    path: str, offset: int = 0
) -> tuple[list[dict[str, Any]], int, bool]:
    """Parse transcript rows from a byte offset, returning rows, end offset, and whether the offset was honored."""
    if not path:
        return [], 0, False
    rows = []
    try:
        resolved = Path(path).expanduser()
        if not 0 <= offset <= resolved.stat().st_size:
            offset = 0
        end = offset
        with resolved.open("rb") as handle:
            handle.seek(offset)
            for line in handle:
                if not line.endswith(b"\n"):
                    break
                end += len(line)
                try:
                    row = json.loads(line.decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                if isinstance(row, dict) and row.get("uuid"):
                    rows.append(row)
    except OSError:
        return [], offset, False
    return rows, end, offset > 0


def _active_transcript_chain(
    rows: list[dict[str, Any]], session_id: str
) -> list[dict[str, Any]]:
    """Follow the current Claude conversation branch from its latest record."""
    by_uuid = {str(row["uuid"]): row for row in rows if row.get("uuid")}
    leaf = next(
        (
            row
            for row in reversed(rows)
            if not row.get("isSidechain")
            and str(row.get("sessionId") or "") == session_id
        ),
        None,
    )
    if leaf is None:
        return []

    chain = []
    seen = set()
    current = leaf
    while current is not None:
        uuid = str(current.get("uuid") or "")
        if not uuid or uuid in seen:
            break
        seen.add(uuid)
        chain.append(current)
        current = by_uuid.get(str(current.get("parentUuid") or ""))
    chain.reverse()
    return chain


def _human_prompt_text(row: dict[str, Any]) -> str:
    if row.get("type") != "user":
        return ""
    origin = row.get("origin") or {}
    if isinstance(origin, dict) and origin.get("kind") not in {None, "human"}:
        return ""
    message = row.get("message") or {}
    content = message.get("content") if isinstance(message, dict) else None
    if not isinstance(content, str):
        return ""
    text = redact(content).strip()
    if text.startswith("<!-- attach -->"):
        text = text.removeprefix("<!-- attach -->").strip()
    ignored_prefixes = (
        "<local-command-caveat>",
        "<local-command-stdout>",
        "<local-command-stderr>",
        "<command-name>",
        "<system-reminder>",
        "<task-notification>",
    )
    return "" if text.startswith(ignored_prefixes) else text


def _xml_value(text: str, tag: str) -> str:
    match = re.search(fr"<{tag}>(.*?)</{tag}>", text, re.DOTALL)
    return html.unescape(match.group(1).strip()) if match else ""


def _agent_assignment(tool_input: dict[str, Any]) -> str:
    prompt = redact(tool_input.get("prompt", "")).strip()
    if not prompt:
        return ""
    agent_type = redact(tool_input.get("subagent_type", "agent")).strip() or "agent"
    description = redact(tool_input.get("description", "")).strip()
    heading = f"Subagent assignment ({agent_type}"
    if description:
        heading += f": {description}"
    return f"{heading}):\n{prompt}"


def _agent_response(tool_input: dict[str, Any], result: str) -> str:
    result = redact(result).strip()
    if not result or result.startswith("Async agent launched successfully."):
        return ""
    agent_type = redact(tool_input.get("subagent_type", "agent")).strip() or "agent"
    description = redact(tool_input.get("description", "")).strip()
    heading = f"Subagent response ({agent_type}"
    if description:
        heading += f": {description}"
    return f"{heading}):\n{result}"


def _tool_result_text(block: dict[str, Any]) -> str:
    return _message_content_text(block.get("content"))


def transcript_extraction_messages(
    transcript_path: str,
    session_id: str,
    *,
    previous_leaf_uuid: str = "",
    prompt_hint: str = "",
    fallback_assistant_message: str = "",
    label_final_response: bool = False,
    start_offset: int = 0,
) -> tuple[list[dict[str, str]], str, int]:
    """Read the meaningful part of the current Claude exchange."""
    rows, end_offset, resumed = _transcript_rows(transcript_path, start_offset)
    chain = _active_transcript_chain(rows, session_id)
    if not chain:
        if resumed:
            return [], previous_leaf_uuid, end_offset
        fallback = redact(fallback_assistant_message).strip()
        return (
            ([{"role": "assistant", "content": f"Main Claude response:\n{fallback}"}]
             if fallback
             else []),
            "",
            end_offset,
        )

    leaf_uuid = str(chain[-1].get("uuid") or "")
    if previous_leaf_uuid and leaf_uuid == previous_leaf_uuid:
        return [], leaf_uuid, end_offset
    start = 0
    if previous_leaf_uuid:
        for index, row in enumerate(chain):
            if str(row.get("uuid") or "") == previous_leaf_uuid:
                start = index + 1
                break
        else:
            previous_leaf_uuid = ""
    if not previous_leaf_uuid and not resumed:
        prompt_hint = redact(prompt_hint).strip()
        candidates = [
            index
            for index, row in enumerate(chain)
            if _human_prompt_text(row)
            and (
                not prompt_hint
                or _human_prompt_text(row) == prompt_hint
            )
        ]
        task_notifications = [
            index
            for index, row in enumerate(chain)
            if isinstance((row.get("message") or {}).get("content"), str)
            and (row.get("message") or {})["content"].startswith("<task-notification>")
        ]
        if candidates:
            start = candidates[-1]
        elif task_notifications:
            start = task_notifications[-1]

    tool_uses: dict[str, tuple[str, dict[str, Any]]] = {}
    for row in chain:
        message = row.get("message") or {}
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            tool_id = str(block.get("id") or "")
            tool_input = block.get("input") or {}
            if tool_id and isinstance(tool_input, dict):
                tool_uses[tool_id] = (str(block.get("name") or ""), tool_input)

    output: list[dict[str, str]] = []

    def append(role: str, content: str) -> None:
        content = redact(content).strip()
        if content:
            output.append({"role": role, "content": content})

    for row in chain[start:]:
        message = row.get("message") or {}
        if not isinstance(message, dict):
            continue
        role = str(message.get("role") or "")
        content = message.get("content")

        if role == "user" and isinstance(content, str):
            if content.startswith("<task-notification>"):
                if _xml_value(content, "status") != "completed":
                    continue
                tool_id = _xml_value(content, "tool-use-id")
                tool = tool_uses.get(tool_id)
                result = _xml_value(content, "result")
                if tool and tool[0] == "Agent" and result:
                    assignment = _agent_assignment(tool[1])
                    response = _agent_response(tool[1], result)
                    append("assistant", assignment)
                    append("assistant", response)
                continue
            human = _human_prompt_text(row)
            if human:
                append("user", human)
            continue

        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if role == "assistant" and block_type == "text":
                append("assistant", str(block.get("text") or ""))
                continue
            if role != "user" or block_type != "tool_result":
                continue

            tool_id = str(block.get("tool_use_id") or "")
            tool = tool_uses.get(tool_id)
            if not tool:
                continue
            name, tool_input = tool
            result = _tool_result_text(block)
            failed = bool(block.get("is_error"))
            if name == "Agent" and not failed:
                response = _agent_response(tool_input, result)
                if response:
                    append("assistant", _agent_assignment(tool_input))
                    append("assistant", response)
            elif name == "AskUserQuestion" and result and not failed:
                append("user", f"User answers to Claude's questions:\n{result}")
            elif name == "ExitPlanMode" and not failed:
                plan = redact(tool_input.get("plan", "")).strip()
                if plan:
                    append("assistant", f"Approved implementation plan:\n{plan}")

    fallback = redact(fallback_assistant_message).strip()
    if fallback:
        labeled = f"Main Claude response:\n{fallback}"
        for message in reversed(output):
            if message["role"] == "assistant" and message["content"] == fallback:
                message["content"] = labeled
                break
        else:
            append("assistant", labeled)
    elif label_final_response:
        last_message = chain[-1].get("message") or {}
        last_content = (
            last_message.get("content") if isinstance(last_message, dict) else None
        )
        final_parts = [
            redact(block.get("text", "")).strip()
            for block in (last_content if isinstance(last_content, list) else [])
            if isinstance(block, dict)
            and block.get("type") == "text"
            and redact(block.get("text", "")).strip()
        ]
        for start in range(len(output) - len(final_parts), -1, -1):
            candidate = output[start : start + len(final_parts)]
            if final_parts and [item["content"] for item in candidate] == final_parts:
                candidate[0]["content"] = (
                    f"Main Claude response:\n{candidate[0]['content']}"
                )
                break
    return output, leaf_uuid, end_offset


def record_stop(
    store: EvidenceStore, hook_input: dict[str, Any]
) -> tuple[RepoContext, str]:
    session_id = _session_id(hook_input)
    repo = store.repo_for_session(session_id, hook_input.get("cwd"))
    message = bounded(hook_input.get("last_assistant_message", ""), MAX_ASSISTANT_CHARS)
    previous_stop = store.latest_event_payload(
        repo.identity, session_id, "assistant_stop"
    )
    latest_prompt = store.latest_event_payload(repo.identity, session_id, "user_prompt")
    transcript_path = str(hook_input.get("transcript_path") or "")
    previous_offset = previous_stop.get("transcript_offset")
    start_offset = (
        previous_offset
        if isinstance(previous_offset, int)
        and str(previous_stop.get("transcript_path") or "") == transcript_path
        else 0
    )
    transcript_messages, leaf_uuid, end_offset = transcript_extraction_messages(
        transcript_path,
        session_id,
        previous_leaf_uuid=str(previous_stop.get("transcript_leaf_uuid") or ""),
        prompt_hint=str(latest_prompt.get("text") or ""),
        fallback_assistant_message=message,
        label_final_response=True,
        start_offset=start_offset,
    )
    if transcript_messages:
        payload: dict[str, Any] = {
            "text": message,
            "transcript_messages": transcript_messages,
        }
        if leaf_uuid:
            payload["transcript_leaf_uuid"] = leaf_uuid
        if transcript_path:
            payload["transcript_path"] = transcript_path
            payload["transcript_offset"] = end_offset
        store.record_event(
            repo, session_id, "assistant_stop", payload
        )
    return repo, session_id
