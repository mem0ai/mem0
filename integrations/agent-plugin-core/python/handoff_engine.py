#!/usr/bin/env python3
"""Save and resume full, host-neutral session context as private local resources.

Native readers and SDK adapters supply conversation items. This engine validates
and stores them without model calls, summarization, or execution of the history.
Any host can list project resources and resume their complete historical context.
"""

# Adapted from mem0ai/memo at aeeb1593284d1d2fca3b4bcf1e32ea10f71df549 (Apache-2.0).
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import uuid
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

FORMAT_VERSION = "mem0.session-handoff.v1"
DEFAULT_BUNDLE_DIR = Path.home() / ".mem0" / "handoffs"
IMAGE_EXTENSIONS = {
    "image/gif": "gif",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


class HandoffError(RuntimeError):
    """A source session cannot be transferred without losing state."""


@dataclass(frozen=True)
class SourceInfo:
    path: str
    sha256: str
    session_id: str
    title: str
    cwd: str
    leaf_uuid: str
    compact_boundary_uuid: str | None
    first_imported_uuid: str
    last_imported_uuid: str
    project_cwd: str | None = None
    host: str = "claude-code"


@dataclass
class HandoffPlan:
    source: SourceInfo
    items: list[dict[str, Any]]
    source_records: int
    active_records: int
    imported_records: int
    hidden_reasoning_blocks_skipped: int
    approximate_tokens: int
    warnings: list[str]

    def bundle(self) -> dict[str, Any]:
        return {
            "format": FORMAT_VERSION,
            "source": asdict(self.source),
            "items": self.items,
            "counts": {
                "source_records": self.source_records,
                "active_records": self.active_records,
                "imported_records": self.imported_records,
                "responses_items": len(self.items),
                "hidden_reasoning_blocks_skipped": self.hidden_reasoning_blocks_skipped,
                "approximate_tokens": self.approximate_tokens,
            },
            "warnings": self.warnings,
        }


def _stable_jsonl(path: Path) -> tuple[list[dict[str, Any]], str]:
    before = path.stat()
    raw = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise HandoffError(f"Source session changed while it was being read: {path}")
    if raw and not raw.endswith(b"\n"):
        raise HandoffError(
            "The final JSONL record is incomplete. Finish or stop the active source response before transferring it."
        )

    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(raw.splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise HandoffError(f"Invalid source JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(record, dict):
            raise HandoffError(f"Source JSONL record is not an object at {path}:{line_number}.")
        records.append(record)
    if not records:
        raise HandoffError(f"Source session is empty: {path}")
    return records, hashlib.sha256(raw).hexdigest()


def _resolve_session(value: str, projects_dir: Path) -> Path:
    supplied = Path(value).expanduser()
    if supplied.is_file():
        return supplied.resolve()

    matches = list(projects_dir.glob(f"*/{value}.jsonl"))
    if not matches:
        raise HandoffError(
            f"No Claude session named {value!r} exists below {projects_dir}. "
            "Pass the session ID or its full JSONL path."
        )
    if len(matches) != 1:
        joined = "\n".join(f"  {path}" for path in matches)
        raise HandoffError(f"Session ID {value!r} is ambiguous:\n{joined}")
    return matches[0].resolve()


def _active_chain(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    with_uuid = [
        record for record in records if isinstance(record.get("uuid"), str) and record.get("isSidechain") is not True
    ]
    if not with_uuid:
        raise HandoffError("Claude session has no main-agent conversation records.")

    by_uuid = {record["uuid"]: record for record in with_uuid}
    leaf = with_uuid[-1]
    chain: list[dict[str, Any]] = []
    seen: set[str] = set()
    current: dict[str, Any] | None = leaf
    while current is not None:
        uuid = current["uuid"]
        if uuid in seen:
            raise HandoffError(f"Claude session contains a parent cycle at {uuid}.")
        seen.add(uuid)
        chain.append(current)
        parent_uuid = current.get("parentUuid")
        if parent_uuid is None:
            break
        current = by_uuid.get(parent_uuid)
        if current is None:
            raise HandoffError(f"Claude's active branch references missing parent {parent_uuid}.")
    chain.reverse()
    return chain


def _after_latest_compaction(
    chain: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    compact_index: int | None = None
    for index, record in enumerate(chain):
        if record.get("type") == "system" and record.get("subtype") == "compact_boundary":
            compact_index = index
    if compact_index is None:
        imported = chain
        compact_uuid = None
    else:
        imported = chain[compact_index + 1 :]
        compact_uuid = chain[compact_index]["uuid"]
        if not imported or imported[0].get("isCompactSummary") is not True:
            raise HandoffError(f"Claude compaction {compact_uuid} has no following compact summary.")
    imported = [record for record in imported if record.get("type") != "system"]
    if not imported:
        raise HandoffError("Claude's active state contains no transferable records.")
    return imported, compact_uuid


def _tool_result_ids(record: dict[str, Any]) -> set[str]:
    if record.get("type") != "user":
        return set()
    content = (record.get("message") or {}).get("content")
    if not isinstance(content, list):
        return set()
    return {
        str(block["tool_use_id"])
        for block in content
        if isinstance(block, dict) and block.get("type") == "tool_result" and block.get("tool_use_id")
    }


def _tool_call_ids(records: list[dict[str, Any]]) -> set[str]:
    call_ids: set[str] = set()
    for record in records:
        if record.get("type") != "assistant":
            continue
        content = (record.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        call_ids.update(
            str(block["id"])
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id")
        )
    return call_ids


def _merge_parallel_tool_results(
    active_records: list[dict[str, Any]], all_records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Restore sibling tool results that Claude stores outside the parent chain.

    Parallel Claude tool calls form a fork: later calls remain on the parent
    chain, while earlier results can be sibling records. Claude sends all of
    those results back to the model. Insert them together immediately after the
    assistant response that issued the calls.
    """
    results_by_call: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for source_index, record in enumerate(all_records):
        for call_id in _tool_result_ids(record):
            results_by_call.setdefault(call_id, []).append((source_index, record))

    merged: list[dict[str, Any]] = []
    inserted_result_uuids: set[str] = set()
    index = 0
    while index < len(active_records):
        record = active_records[index]
        record_uuid = str(record.get("uuid") or "")
        if record_uuid in inserted_result_uuids:
            index += 1
            continue
        if record.get("type") != "assistant":
            merged.append(record)
            index += 1
            continue

        message_id = (record.get("message") or {}).get("id")
        group = [record]
        index += 1
        while index < len(active_records):
            candidate = active_records[index]
            candidate_id = (candidate.get("message") or {}).get("id")
            if candidate.get("type") != "assistant" or not message_id or candidate_id != message_id:
                break
            group.append(candidate)
            index += 1
        merged.extend(group)

        matching_results: list[tuple[int, dict[str, Any]]] = []
        for call_id in _tool_call_ids(group):
            matching_results.extend(results_by_call.get(call_id, []))
        for _, result in sorted(matching_results, key=lambda pair: pair[0]):
            result_uuid = str(result.get("uuid") or "")
            if result_uuid and result_uuid not in inserted_result_uuids:
                merged.append(result)
                inserted_result_uuids.add(result_uuid)
    return merged


def _image_payload(source: Any, context: str) -> tuple[str, str]:
    if not isinstance(source, dict) or source.get("type") != "base64":
        raise HandoffError(f"{context} is not stored as transferable base64 data.")
    media_type = str(source.get("media_type") or "").lower()
    data = source.get("data")
    if media_type not in IMAGE_EXTENSIONS or not isinstance(data, str) or not data:
        raise HandoffError(f"{context} has an unsupported or missing image type.")
    return media_type, data


def _data_url_payload(image_url: Any, context: str) -> tuple[str, str]:
    if not isinstance(image_url, str):
        raise HandoffError(f"{context} has no transferable image data.")
    match = re.fullmatch(r"data:([^;,]+);base64,(.+)", image_url, flags=re.DOTALL)
    if not match:
        raise HandoffError(f"{context} is not stored as transferable base64 data.")
    media_type = match.group(1).lower()
    if media_type not in IMAGE_EXTENSIONS:
        raise HandoffError(f"{context} has unsupported image type {media_type!r}.")
    return media_type, match.group(2)


def _message(role: str, parts: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "message", "role": role, "content": parts}


def _attachment_item(record: dict[str, Any]) -> dict[str, Any] | None:
    attachment = record.get("attachment")
    if not isinstance(attachment, dict):
        raise HandoffError(f"Claude attachment {record.get('uuid')} has no payload.")

    attachment_type = attachment.get("type")
    filename = str(attachment.get("filename") or attachment.get("displayPath") or "unknown")
    content = attachment.get("content")
    if attachment_type == "file" and isinstance(content, dict):
        file_payload = content.get("file") if content.get("type") == "text" else None
        if isinstance(file_payload, dict) and isinstance(file_payload.get("content"), str):
            text = file_payload["content"]
            display = str(file_payload.get("filePath") or filename)
            wrapped = f'<claude_attachment path="{display}">\n{text}\n</claude_attachment>'
            return _message("user", [{"type": "input_text", "text": wrapped}])

    if attachment_type == "image" and isinstance(content, dict):
        image_url = content.get("image_url") or content.get("data")
        if isinstance(image_url, str) and image_url.startswith("data:"):
            return _message("user", [{"type": "input_image", "image_url": image_url}])

    if attachment_type in {"file", "image"}:
        raise HandoffError(f"Claude {attachment_type} attachment {record.get('uuid')} has an unsupported payload.")

    # Claude also records its own skill list, tool availability, permissions,
    # token reminders, hooks, and task status as attachments. Those configure
    # Claude's harness; they are not part of the user's project conversation and
    # must not become user historical messages.
    return None


def _assistant_items(records: list[dict[str, Any]], calls: dict[str, str]) -> tuple[list[dict[str, Any]], int]:
    items: list[dict[str, Any]] = []
    skipped_reasoning = 0
    text_parts: list[dict[str, Any]] = []

    def flush_text() -> None:
        if text_parts:
            items.append(_message("assistant", list(text_parts)))
            text_parts.clear()

    for record in records:
        content = (record.get("message") or {}).get("content", [])
        if isinstance(content, str):
            text_parts.append({"type": "output_text", "text": content})
            continue
        if not isinstance(content, list):
            raise HandoffError(f"Claude assistant record {record.get('uuid')} has invalid content.")
        for block in content:
            if not isinstance(block, dict):
                raise HandoffError(f"Claude assistant record {record.get('uuid')} has invalid block.")
            kind = block.get("type")
            if kind == "thinking" or kind == "redacted_thinking":
                skipped_reasoning += 1
                continue
            if kind == "text":
                text_parts.append({"type": "output_text", "text": str(block.get("text", ""))})
                continue
            if kind == "tool_use":
                flush_text()
                call_id = str(block.get("id") or "")
                name = str(block.get("name") or "")
                if not call_id or not name:
                    raise HandoffError(f"Claude tool call in {record.get('uuid')} has no ID or name.")
                if call_id in calls:
                    raise HandoffError(f"Claude tool call ID is duplicated: {call_id}")
                calls[call_id] = name
                items.append(
                    {
                        "type": "function_call",
                        "call_id": call_id,
                        "name": name,
                        "arguments": json.dumps(
                            block.get("input", {}),
                            ensure_ascii=False,
                            separators=(",", ":"),
                        ),
                    }
                )
                continue
            raise HandoffError(f"Unsupported Claude assistant block {kind!r} in {record.get('uuid')}.")
    flush_text()
    return items, skipped_reasoning


def _user_items(record: dict[str, Any], calls: dict[str, str], completed_calls: set[str]) -> list[dict[str, Any]]:
    if record.get("isMeta") is True:
        return []
    content = (record.get("message") or {}).get("content")
    if isinstance(content, str):
        return [_message("user", [{"type": "input_text", "text": content}])]
    if not isinstance(content, list):
        raise HandoffError(f"Claude user record {record.get('uuid')} has invalid content.")

    items: list[dict[str, Any]] = []
    user_parts: list[dict[str, Any]] = []

    def flush_user() -> None:
        if user_parts:
            items.append(_message("user", list(user_parts)))
            user_parts.clear()

    for block in content:
        if not isinstance(block, dict):
            raise HandoffError(f"Claude user record {record.get('uuid')} has invalid block.")
        kind = block.get("type")
        if kind == "text":
            user_parts.append({"type": "input_text", "text": str(block.get("text", ""))})
            continue
        if kind == "image":
            source = block.get("source") or {}
            if source.get("type") == "base64" and source.get("data") and source.get("media_type"):
                user_parts.append(
                    {
                        "type": "input_image",
                        "image_url": f"data:{source['media_type']};base64,{source['data']}",
                    }
                )
                continue
            raise HandoffError(f"Claude image in {record.get('uuid')} is not stored as transferable base64 data.")
        if kind == "tool_result":
            flush_user()
            call_id = str(block.get("tool_use_id") or "")
            if not call_id:
                raise HandoffError(f"Claude tool result in {record.get('uuid')} has no call ID.")
            if call_id not in calls:
                raise HandoffError(f"Claude tool result {call_id} has no matching call in the active state.")
            if call_id in completed_calls:
                raise HandoffError(f"Claude tool result is duplicated: {call_id}")
            completed_calls.add(call_id)
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "name": calls[call_id],
                    "output": block.get("content"),
                }
            )
            continue
        raise HandoffError(f"Unsupported Claude user block {kind!r} in {record.get('uuid')}.")
    flush_user()
    return items


def _responses_items(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    items: list[dict[str, Any]] = []
    calls: dict[str, str] = {}
    completed_calls: set[str] = set()
    skipped_reasoning = 0

    index = 0
    while index < len(records):
        record = records[index]
        record_type = record.get("type")
        if record_type == "assistant":
            message_id = (record.get("message") or {}).get("id")
            group = [record]
            index += 1
            while index < len(records):
                candidate = records[index]
                if candidate.get("type") != "assistant":
                    break
                candidate_id = (candidate.get("message") or {}).get("id")
                if not message_id or candidate_id != message_id:
                    break
                group.append(candidate)
                index += 1
            assistant_items, skipped = _assistant_items(group, calls)
            items.extend(assistant_items)
            skipped_reasoning += skipped
            continue
        if record_type == "user":
            items.extend(_user_items(record, calls, completed_calls))
        elif record_type == "attachment":
            attachment_item = _attachment_item(record)
            if attachment_item is not None:
                items.append(attachment_item)
        elif record_type not in {"system"}:
            raise HandoffError(f"Unsupported model-visible Claude record {record_type!r} at {record.get('uuid')}.")
        index += 1

    unfinished = sorted(set(calls) - completed_calls)
    if unfinished:
        joined = ", ".join(unfinished[:5])
        raise HandoffError(
            f"Claude's active state ends with unfinished tool call(s): {joined}. "
            "Finish or stop the Claude turn before transferring it."
        )
    if not items:
        raise HandoffError("Claude's active state produced no handoff history items.")
    return items, skipped_reasoning


def _without_image_payloads(value: Any) -> Any:
    if isinstance(value, list):
        return [_without_image_payloads(item) for item in value]
    if not isinstance(value, dict):
        return value

    cleaned = {key: _without_image_payloads(item) for key, item in value.items()}
    if cleaned.get("type") == "input_image" and isinstance(cleaned.get("image_url"), str):
        cleaned["image_url"] = "[Image saved locally during handoff]"
    if cleaned.get("type") == "image" and isinstance(cleaned.get("source"), dict):
        source = dict(cleaned["source"])
        if source.get("type") == "base64" and "data" in source:
            source["data"] = "[Image saved locally during handoff]"
        cleaned["source"] = source
    return cleaned


def _token_count(value: Any) -> int:
    text = json.dumps(_without_image_payloads(value), ensure_ascii=False, separators=(",", ":"))
    return (len(text) + 3) // 4


def build_plan(session: str, projects_dir: Path) -> HandoffPlan:
    path = _resolve_session(session, projects_dir)
    records, sha256 = _stable_jsonl(path)
    chain = _active_chain(records)
    imported, compact_uuid = _after_latest_compaction(chain)
    imported = _merge_parallel_tool_results(imported, records)
    items, skipped_reasoning = _responses_items(imported)

    session_id = next(
        (str(record["sessionId"]) for record in reversed(records) if record.get("sessionId")),
        path.stem,
    )
    title = next(
        (
            str(record["customTitle"])
            for record in reversed(records)
            if record.get("type") == "custom-title" and record.get("customTitle")
        ),
        f"Claude session {session_id[:8]}",
    )
    cwd = next(
        (str(record["cwd"]) for record in chain if record.get("cwd")),
        "",
    )
    if not cwd:
        raise HandoffError("Claude session does not record its working directory.")

    warnings: list[str] = []
    if skipped_reasoning:
        warnings.append(f"Skipped {skipped_reasoning} Claude hidden-reasoning block(s); they are not portable.")

    source = SourceInfo(
        path=str(path),
        sha256=sha256,
        session_id=session_id,
        title=title,
        cwd=str(Path(cwd).resolve()),
        leaf_uuid=chain[-1]["uuid"],
        compact_boundary_uuid=compact_uuid,
        first_imported_uuid=imported[0]["uuid"],
        last_imported_uuid=imported[-1]["uuid"],
        project_cwd=_git_root(Path(cwd)),
    )
    return HandoffPlan(
        source=source,
        items=items,
        source_records=len(records),
        active_records=len(chain),
        imported_records=len(imported),
        hidden_reasoning_blocks_skipped=skipped_reasoning,
        approximate_tokens=_token_count(items),
        warnings=warnings,
    )


def _write_private(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(body)
        os.link(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_bundle(plan: HandoffPlan, path: Path) -> Path:
    path = path.expanduser().resolve()
    _validate_items(plan.items)
    _write_private(path, json.dumps(plan.bundle(), ensure_ascii=False))
    return path


def _validate_image_data(encoded: str) -> None:
    try:
        if not base64.b64decode(encoded, validate=True):
            raise ValueError("empty image")
    except (ValueError, binascii.Error) as exc:
        raise HandoffError("Invalid handoff image data.") from exc


def _validate_tool_output(output: Any) -> None:
    for part in output if isinstance(output, list) else [output]:
        if isinstance(part, dict) and part.get("type") == "image":
            _, encoded = _image_payload(part.get("source"), "Handoff tool result image")
            _validate_image_data(encoded)


def _validate_items(items: Any) -> None:
    if not isinstance(items, list) or not items:
        raise HandoffError("Handoff bundle contains no history items.")
    calls: dict[str, str] = {}
    completed: set[str] = set()
    saw_user = False
    for item in items:
        if not isinstance(item, dict):
            raise HandoffError("Invalid handoff history item.")
        kind = item.get("type")
        status = item.get("status")
        if (
            not isinstance(kind, str)
            or (status is not None and not isinstance(status, str))
            or status in {"incomplete", "in_progress"}
        ):
            raise HandoffError("Invalid or incomplete handoff history item.")
        if kind == "message":
            role = item.get("role")
            parts = item.get("content")
            if (
                not isinstance(role, str)
                or role not in {"user", "assistant"}
                or not isinstance(parts, list)
                or not parts
            ):
                raise HandoffError("Invalid handoff message role or content.")
            saw_user = saw_user or role == "user"
            for part in parts:
                if not isinstance(part, dict) or not isinstance(part.get("type"), str):
                    raise HandoffError("Invalid handoff message part.")
                if part.get("type") in {"input_text", "output_text"} and isinstance(part.get("text"), str):
                    continue
                if part.get("type") == "input_image":
                    _, encoded = _data_url_payload(part.get("image_url"), "Handoff image")
                    _validate_image_data(encoded)
                    continue
                raise HandoffError("Unsupported handoff message part.")
        elif kind == "function_call":
            call_id, name, arguments = item.get("call_id"), item.get("name"), item.get("arguments")
            if not isinstance(call_id, str) or not call_id or not isinstance(name, str) or not name:
                raise HandoffError("Invalid handoff tool call ID or name.")
            if call_id in calls or not isinstance(arguments, str):
                raise HandoffError("Duplicate or invalid handoff tool call.")
            try:
                json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise HandoffError("Handoff tool arguments are not JSON.") from exc
            calls[call_id] = name
        elif kind == "function_call_output":
            call_id = item.get("call_id")
            if not isinstance(call_id, str) or call_id not in calls or call_id in completed:
                raise HandoffError("Unmatched or duplicate handoff tool result.")
            if "output" not in item:
                raise HandoffError("Handoff tool result has no output.")
            _validate_tool_output(item["output"])
            completed.add(call_id)
            item.setdefault("name", calls[call_id])
        else:
            raise HandoffError(f"Unsupported handoff item type: {kind!r}.")
    if set(calls) != completed:
        raise HandoffError("Session has unfinished tool calls; finish or stop the source turn before handoff.")
    if not saw_user:
        raise HandoffError("Handoff contains no user message.")


def plan_from_bundle(payload: Any) -> HandoffPlan:
    formats = {FORMAT_VERSION, "mem0.claude-to-codex.v1", "memo.claude-to-codex.v1"}
    if not isinstance(payload, dict) or not isinstance(payload.get("format"), str) or payload["format"] not in formats:
        raise HandoffError("Unsupported handoff bundle format.")
    source_payload = payload.get("source")
    items = payload.get("items")
    warnings = payload.get("warnings", [])
    if (
        not isinstance(source_payload, dict)
        or not isinstance(warnings, list)
        or any(not isinstance(warning, str) for warning in warnings)
    ):
        raise HandoffError("Handoff bundle has no source or has invalid warnings.")
    _validate_items(items)
    try:
        fields = dict(source_payload)
        if "codex_cwd" in fields:
            fields.setdefault("project_cwd", fields.pop("codex_cwd"))
        legacy = payload["format"] != FORMAT_VERSION
        fields.setdefault("host", "claude-code" if legacy else "")
        for key in ("host", "session_id", "title", "cwd"):
            if not isinstance(fields.get(key), str) or not fields[key].strip():
                raise ValueError(f"invalid source field: {key}")
        if not re.fullmatch(r"[a-z][a-z0-9-]*", fields["host"]):
            raise ValueError("invalid source host")
        fields.setdefault("path", f"{fields['host']}:{fields['session_id']}")
        fields.setdefault("sha256", hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest())
        fields.setdefault("leaf_uuid", str(len(items)))
        fields.setdefault("first_imported_uuid", "1")
        fields.setdefault("last_imported_uuid", str(len(items)))
        fields.setdefault("compact_boundary_uuid", None)
        source = SourceInfo(**fields)
        for key, value in asdict(source).items():
            if value is None and key in {"project_cwd", "compact_boundary_uuid"}:
                continue
            if not isinstance(value, str):
                raise ValueError(f"invalid source field: {key}")
        if not re.fullmatch(r"[0-9a-f]{64}", source.sha256):
            raise ValueError("invalid source digest")
        counts = payload.get("counts", {})
        if not isinstance(counts, dict) or any(type(value) is not int or value < 0 for value in counts.values()):
            raise ValueError("invalid counts")
        return HandoffPlan(
            source=source,
            items=items,
            source_records=int(counts.get("source_records", len(items))),
            active_records=int(counts.get("active_records", len(items))),
            imported_records=int(counts.get("imported_records", len(items))),
            hidden_reasoning_blocks_skipped=int(counts.get("hidden_reasoning_blocks_skipped", 0)),
            approximate_tokens=_token_count(items),
            warnings=warnings,
        )
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise HandoffError("Handoff bundle is incomplete or has invalid source fields.") from exc


def load_bundle(path: Path) -> HandoffPlan:
    try:
        text = sys.stdin.read() if str(path) == "-" else path.expanduser().resolve().read_text(encoding="utf-8")
        return plan_from_bundle(json.loads(text))
    except json.JSONDecodeError as exc:
        raise HandoffError(f"Invalid handoff bundle JSON: {path}") from exc


def _git_root(cwd: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    root = Path(completed.stdout.strip()).resolve()
    return str(root) if root.is_dir() else None


def _project_cwd(cwd: Path) -> str:
    cwd = cwd.expanduser().resolve()
    if not cwd.is_dir():
        raise HandoffError(f"Working directory does not exist: {cwd}")
    return _git_root(cwd) or str(cwd)


def _with_cwd(plan: HandoffPlan, cwd: Path | None) -> HandoffPlan:
    source_cwd = Path(plan.source.cwd).expanduser().resolve()
    project = _project_cwd(cwd or Path(plan.source.project_cwd or source_cwd))
    return replace(plan, source=replace(plan.source, cwd=str(source_cwd), project_cwd=project))


def save_resource(plan: HandoffPlan) -> Path:
    """Publish a complete private resource atomically, never replacing a saved file."""
    plan = _with_cwd(plan, None)
    name = f"{plan.source.host}-{uuid.uuid4().hex}.json"
    return write_bundle(plan, DEFAULT_BUNDLE_DIR / name)


def _resource_metadata(path: Path, plan: HandoffPlan) -> dict[str, Any]:
    return {
        "resource": str(path),
        "title": plan.source.title,
        "source_host": plan.source.host,
        "session_id": plan.source.session_id,
        "project_cwd": plan.source.project_cwd or plan.source.cwd,
    }


def list_resources(cwd: Path) -> list[dict[str, Any]]:
    project = _project_cwd(cwd)
    resources = []
    for path in sorted(DEFAULT_BUNDLE_DIR.glob("*.json")):
        try:
            plan = load_bundle(path)
        except (HandoffError, OSError, UnicodeError) as exc:
            raise HandoffError(f"Cannot read saved handoff resource {path}: {exc}") from exc
        recorded = Path(plan.source.project_cwd or plan.source.cwd).expanduser().resolve()
        if str(recorded) == project or (recorded.is_dir() and _project_cwd(recorded) == project):
            resources.append(_resource_metadata(path.resolve(), plan))
    return resources


def resume_resource(path: Path, cwd: Path) -> dict[str, Any]:
    """Return validated history as data; the receiving host decides how to continue."""
    project = _project_cwd(cwd)
    path = path.expanduser().resolve()
    plan = load_bundle(path)
    return {
        "resource": str(path),
        "context_type": "historical_session",
        "project_cwd": project,
        "handoff": plan.bundle(),
    }


def _parse_args(argv: Iterable[str] | None, default_source: str | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--save", action="store_true", help="Save a complete private handoff resource")
    action.add_argument("--list", action="store_true", help="List saved handoffs for the current project")
    action.add_argument("--resume", type=Path, help="Return the full saved context for any host")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--session", help="Native transcript path (Claude also accepts its session ID)")
    source.add_argument("--bundle", type=Path, help="Neutral context JSON path, or - for stdin")
    parser.add_argument(
        "--source",
        default=default_source,
        choices=("claude-code", "cursor", "codex", "kimi", "antigravity", "openclaw", "pi-agent"),
    )
    parser.add_argument("--title", help="Title of the saved resource")
    parser.add_argument("--claude-projects-dir", type=Path, default=Path.home() / ".claude" / "projects")
    parser.add_argument("--cwd", type=Path, help="Current project directory (defaults to source on save)")
    parser.add_argument(
        "--command-output", action="store_true", help="Readable save/list output; resume stays full JSON"
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None, default_source: str | None = None) -> int:
    args = _parse_args(argv, default_source)
    try:
        if not args.save and (args.session or args.bundle or args.title):
            raise HandoffError("--session, --bundle, and --title are only valid with --save.")
        if args.resume:
            output = resume_resource(args.resume, args.cwd or Path.cwd())
        elif args.list:
            resources = list_resources(args.cwd or Path.cwd())
            if args.command_output:
                print(
                    "\n".join(f"{item['title']} — {item['resource']}" for item in resources)
                    or "No saved handoff resources for this project."
                )
                return 0
            output = {"resources": resources}
        else:
            if args.bundle:
                plan = load_bundle(args.bundle)
            elif not args.session:
                raise HandoffError("--save requires --session or --bundle.")
            elif not args.source:
                raise HandoffError("--source is required with --session.")
            elif args.source == "claude-code":
                plan = build_plan(args.session, args.claude_projects_dir)
            else:
                from handoff_sources import read_source

                plan = read_source(args.source, Path(args.session), cwd=args.cwd, title=args.title)
            if args.title:
                plan = replace(plan, source=replace(plan.source, title=args.title))
            plan = _with_cwd(plan, args.cwd)
            path = save_resource(plan)
            if args.command_output:
                print(f"Saved handoff resource: {path}\nResume this resource from any Mem0 plugin.")
                return 0
            output = _resource_metadata(path, plan)
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (HandoffError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        print(f"Handoff failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
