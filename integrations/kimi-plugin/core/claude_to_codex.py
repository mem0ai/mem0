#!/usr/bin/env python3
"""Shared local session-handoff engine and backwards-compatible Claude CLI.

Native readers and SDK adapters supply complete conversation items. This engine
validates and exports their bundles, then uses Codex's native external-session
importer to create a task with visible historical turns. The legacy command
still defaults to reading a Claude Code transcript; session_handoff.py requires
an explicit source host or a neutral bundle.

No model generates a handoff summary. Large imports may use Codex's native
compaction before the new task is returned.
"""

# Adapted from mem0ai/memo at aeeb1593284d1d2fca3b4bcf1e32ea10f71df549 (Apache-2.0).
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import html
import json
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Iterable

FORMAT_VERSION = "mem0.session-handoff.v1"
DEFAULT_CODEX_HOME = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
DEFAULT_BUNDLE_DIR = Path.home() / ".mem0" / "handoffs"
IMPORT_COMPLETED_NOTIFICATION = "externalAgentConfig/import/completed"
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
    codex_cwd: str | None = None
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


@dataclass(frozen=True)
class CodexContextLimits:
    model: str
    context_window: int
    usable_context_window: int
    auto_compact_token_limit: int
    max_context_window: int
    max_usable_context_window: int
    max_auto_compact_token_limit: int


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


def _save_image(
    media_type: str,
    encoded: str,
    asset_dir: Path,
    context: str,
) -> Path:
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HandoffError(f"{context} contains invalid base64 image data.") from exc
    if not payload:
        raise HandoffError(f"{context} contains an empty image.")

    digest = hashlib.sha256(payload).hexdigest()
    asset_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = asset_dir / f"{digest}.{IMAGE_EXTENSIONS[media_type]}"
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise HandoffError(f"The existing handoff image is corrupted: {path}")
        return path

    descriptor, filename = tempfile.mkstemp(prefix=f".{path.name}.", dir=asset_dir)
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
        os.replace(temporary, path)
    except OSError as exc:
        temporary.unlink(missing_ok=True)
        raise HandoffError(f"Could not save the handoff image at {path}: {exc}") from exc
    return path


def _image_reference(
    media_type: str,
    encoded: str,
    asset_dir: Path,
    context: str,
) -> str:
    path = _save_image(media_type, encoded, asset_dir, context)
    return f"[Image saved at {path}]"


def _tool_result_text(value: Any, asset_dir: Path, context: str) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        parts: list[str] = []
        for part in value:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            elif isinstance(part, dict) and part.get("type") == "image":
                media_type, encoded = _image_payload(part.get("source"), context)
                parts.append(_image_reference(media_type, encoded, asset_dir, context))
            else:
                parts.append(json.dumps(part, ensure_ascii=False, separators=(",", ":")))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict) and value.get("type") == "image":
        media_type, encoded = _image_payload(value.get("source"), context)
        return _image_reference(media_type, encoded, asset_dir, context)
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


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
    # must not become user messages in Codex.
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
        raise HandoffError("Claude's active state produced no Codex history items.")
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
    try:
        import tiktoken

        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except ImportError:
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
        codex_cwd=_git_root(Path(cwd)),
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
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def write_bundle(plan: HandoffPlan, path: Path) -> Path:
    path = path.expanduser().resolve()
    _write_private(path, json.dumps(plan.bundle(), ensure_ascii=False))
    return path


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
                    try:
                        if not base64.b64decode(encoded, validate=True):
                            raise ValueError("empty image")
                    except (ValueError, binascii.Error) as exc:
                        raise HandoffError("Invalid handoff image data.") from exc
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
    if not isinstance(source_payload, dict) or not isinstance(warnings, list):
        raise HandoffError("Handoff bundle has no source or has invalid warnings.")
    _validate_items(items)
    try:
        fields = dict(source_payload)
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
            if value is None and key in {"codex_cwd", "compact_boundary_uuid"}:
                continue
            if not isinstance(value, str):
                raise ValueError(f"invalid source field: {key}")
        if not re.fullmatch(r"[0-9a-f]{64}", source.sha256):
            raise ValueError("invalid source digest")
        counts = payload.get("counts", {})
        return HandoffPlan(
            source=source,
            items=items,
            source_records=int(counts.get("source_records", len(items))),
            active_records=int(counts.get("active_records", len(items))),
            imported_records=int(counts.get("imported_records", len(items))),
            hidden_reasoning_blocks_skipped=int(counts.get("hidden_reasoning_blocks_skipped", 0)),
            approximate_tokens=_token_count(items),
            warnings=[str(warning) for warning in warnings],
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
    completed = subprocess.run(
        ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if completed.returncode != 0:
        return None
    root = Path(completed.stdout.strip()).resolve()
    return str(root) if root.is_dir() else None


def _with_cwd(plan: HandoffPlan, cwd: Path | None) -> HandoffPlan:
    source_cwd = Path(plan.source.cwd).expanduser().resolve()
    target = (
        cwd.expanduser().resolve()
        if cwd
        else Path(plan.source.codex_cwd).expanduser().resolve()
        if plan.source.codex_cwd
        else Path(_git_root(source_cwd) or source_cwd)
    )
    if not target.is_dir():
        raise HandoffError(f"Codex working directory does not exist: {target}")
    return replace(plan, source=replace(plan.source, cwd=str(source_cwd), codex_cwd=str(target)))


def _codex_cwd(plan: HandoffPlan) -> str:
    return plan.source.codex_cwd or plan.source.cwd


def _default_bundle_path(plan: HandoffPlan) -> Path:
    session = re.sub(r"[^A-Za-z0-9._-]+", "-", plan.source.session_id).strip(".-")[:80] or "session"
    name = f"{session}-{plan.source.sha256[:12]}.json"
    return DEFAULT_BUNDLE_DIR / name


def _codex_context_limits(codex_home: Path) -> CodexContextLimits:
    try:
        import tomllib
    except ImportError as exc:
        raise HandoffError("Creating a Codex task requires Python 3.11 or newer; rerun with python3.11.") from exc

    codex_home = codex_home.expanduser().resolve()
    config_path = codex_home / "config.toml"
    cache_path = codex_home / "models_cache.json"
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise HandoffError(f"Cannot read Codex configuration at {config_path}: {exc}") from exc
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise HandoffError(f"Cannot read Codex model metadata at {cache_path}: {exc}") from exc

    model = str(config.get("model") or "")
    models = cache.get("models") if isinstance(cache, dict) else None
    if not isinstance(models, list):
        raise HandoffError(f"Codex model metadata has no model list: {cache_path}")
    model_info = next(
        (
            item
            for item in models
            if isinstance(item, dict)
            and (
                item.get("slug") == model
                or item.get("model") == model
                or (not model and item.get("is_default") is True)
            )
        ),
        None,
    )
    if not isinstance(model_info, dict):
        raise HandoffError(f"Codex model {model!r} is missing from {cache_path}; refresh Codex's model list.")
    model = str(model_info.get("slug") or model_info.get("model") or model)

    cached_context = model_info.get("context_window")
    cached_max = model_info.get("max_context_window") or cached_context
    if not isinstance(cached_context, int) or not isinstance(cached_max, int):
        raise HandoffError(f"Codex model {model!r} does not report its context limits.")
    configured_context = config.get("model_context_window")
    context_window = min(configured_context, cached_max) if isinstance(configured_context, int) else cached_context
    effective_percent = model_info.get("effective_context_window_percent", 95)
    if not isinstance(effective_percent, int) or not 1 <= effective_percent <= 100:
        raise HandoffError(f"Codex model {model!r} reports an invalid effective context percentage.")

    context_auto_limit = context_window * 9 // 10
    configured_auto_limit = config.get("model_auto_compact_token_limit")
    auto_compact_limit = (
        min(configured_auto_limit, context_auto_limit) if isinstance(configured_auto_limit, int) else context_auto_limit
    )
    return CodexContextLimits(
        model=model,
        context_window=context_window,
        usable_context_window=context_window * effective_percent // 100,
        auto_compact_token_limit=auto_compact_limit,
        max_context_window=cached_max,
        max_usable_context_window=cached_max * effective_percent // 100,
        max_auto_compact_token_limit=cached_max * 9 // 10,
    )


class CodexAppServer:
    """Small JSON-RPC client for a one-off local Codex app-server process."""

    def __init__(
        self,
        codex_bin: str = "codex",
        context_window_override: int | None = None,
        codex_home: Path = DEFAULT_CODEX_HOME,
    ) -> None:
        resolved = shutil.which(codex_bin)
        if not resolved:
            raise HandoffError(f"Codex executable not found: {codex_bin}")
        command = [resolved]
        if context_window_override is not None:
            command.extend(["-c", f"model_context_window={context_window_override}"])
        command.extend(["app-server", "--stdio"])
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "CODEX_HOME": str(codex_home.expanduser().resolve())},
        )
        self._responses: queue.Queue[dict[str, Any]] = queue.Queue()
        self._notifications: queue.Queue[dict[str, Any]] = queue.Queue()
        self._stderr: list[str] = []
        self._next_id = 1
        threading.Thread(target=self._read_stdout, daemon=True).start()
        threading.Thread(target=self._read_stderr, daemon=True).start()
        try:
            self.request(
                "initialize",
                {
                    "clientInfo": {
                        "name": "mem0_session_handoff",
                        "title": "Mem0 local session handoff",
                        "version": "0.1.0",
                    }
                },
            )
            self.notify("initialized", {})
        except Exception:
            self.close()
            raise

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(message, dict):
                continue
            if "id" in message:
                self._responses.put(message)
            elif "method" in message:
                self._notifications.put(message)

    def _read_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr.append(line.rstrip())

    def _send(self, payload: dict[str, Any]) -> None:
        if self.process.poll() is not None:
            error = "\n".join(self._stderr[-20:])
            raise HandoffError(f"Codex app-server stopped unexpectedly.\n{error}")
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps(payload, separators=(",", ":")) + "\n")
        self.process.stdin.flush()

    def request(self, method: str, params: dict[str, Any], timeout: float = 30) -> Any:
        request_id = self._next_id
        self._next_id += 1
        self._send({"method": method, "id": request_id, "params": params})
        deadline = time.monotonic() + timeout
        deferred: list[dict[str, Any]] = []
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HandoffError(f"Codex app-server timed out on {method}.")
                try:
                    response = self._responses.get(timeout=remaining)
                except queue.Empty as exc:
                    raise HandoffError(f"Codex app-server timed out on {method}.") from exc
                if response.get("id") != request_id:
                    deferred.append(response)
                    continue
                if "error" in response:
                    raise HandoffError(f"Codex {method} failed: {response['error']}")
                return response.get("result")
        finally:
            for response in deferred:
                self._responses.put(response)

    def notify(self, method: str, params: dict[str, Any]) -> None:
        self._send({"method": method, "params": params})

    def wait_for_notification(
        self,
        method: str,
        predicate: Any | None = None,
        timeout: float = 600,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        deferred: list[dict[str, Any]] = []
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise HandoffError(f"Codex app-server timed out waiting for {method}.")
                try:
                    notification = self._notifications.get(timeout=remaining)
                except queue.Empty as exc:
                    raise HandoffError(f"Codex app-server timed out waiting for {method}.") from exc
                if notification.get("method") != method:
                    deferred.append(notification)
                    continue
                params = notification.get("params")
                if predicate is None or predicate(params):
                    return notification
                deferred.append(notification)
        finally:
            for notification in deferred:
                self._notifications.put(notification)

    def wait_for_any_notification(
        self,
        methods: set[str],
        predicate: Any | None = None,
        timeout: float = 600,
    ) -> dict[str, Any]:
        deadline = time.monotonic() + timeout
        deferred: list[dict[str, Any]] = []
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    joined = ", ".join(sorted(methods))
                    raise HandoffError(f"Codex app-server timed out waiting for one of: {joined}.")
                try:
                    notification = self._notifications.get(timeout=remaining)
                except queue.Empty as exc:
                    joined = ", ".join(sorted(methods))
                    raise HandoffError(f"Codex app-server timed out waiting for one of: {joined}.") from exc
                if notification.get("method") not in methods:
                    deferred.append(notification)
                    continue
                params = notification.get("params")
                if predicate is None or predicate(params):
                    return notification
                deferred.append(notification)
        finally:
            for notification in deferred:
                self._notifications.put(notification)

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)

    def __enter__(self) -> "CodexAppServer":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()


def _item_text(item: dict[str, Any], asset_dir: Path) -> tuple[str, str]:
    """Convert one Responses item to a complete visible import message."""
    item_type = item.get("type")
    if item_type == "message":
        role = str(item.get("role") or "")
        if role not in {"user", "assistant"}:
            raise HandoffError(f"Codex's session importer cannot represent role {role!r}.")
        parts: list[str] = []
        for part in item.get("content") or []:
            if not isinstance(part, dict):
                raise HandoffError("A handoff message contains an invalid content item.")
            part_type = part.get("type")
            if part_type in {"input_text", "output_text"}:
                parts.append(str(part.get("text") or ""))
            elif part_type == "input_image":
                media_type, encoded = _data_url_payload(part.get("image_url"), "A Claude message image")
                parts.append(_image_reference(media_type, encoded, asset_dir, "A Claude message image"))
            else:
                raise HandoffError(f"Codex's session importer cannot represent content type {part_type!r}.")
        text = "\n\n".join(part for part in parts if part)
        if not text:
            raise HandoffError("A handoff message contains no transferable text.")
        return role, text

    if item_type == "function_call":
        name = html.escape(str(item.get("name") or "unknown"), quote=True)
        call_id = html.escape(str(item.get("call_id") or "unknown"), quote=True)
        arguments = str(item.get("arguments") or "{}")
        return (
            "assistant",
            f'<tool_call name="{name}" id="{call_id}">\n{arguments}\n</tool_call>',
        )

    if item_type == "function_call_output":
        name = html.escape(str(item.get("name") or "unknown"), quote=True)
        call_id = html.escape(str(item.get("call_id") or "unknown"), quote=True)
        output = _tool_result_text(item.get("output"), asset_dir, f"Claude tool result {call_id}")
        return (
            "assistant",
            f'<tool_result name="{name}" id="{call_id}">\n{output}\n</tool_result>',
        )

    raise HandoffError(f"Codex's session importer cannot represent item type {item_type!r}.")


def _native_import_records(plan: HandoffPlan, asset_dir: Path) -> list[dict[str, Any]]:
    """Build the Claude-shaped history consumed by Codex's native importer."""
    cwd = _codex_cwd(plan)
    records: list[dict[str, Any]] = [
        {
            "type": "custom-title",
            "customTitle": plan.source.title,
            "sessionId": plan.source.session_id,
        }
    ]
    saw_user = False
    for index, item in enumerate(plan.items, 1):
        role, text = _item_text(item, asset_dir)
        saw_user = saw_user or role == "user"
        records.append(
            {
                "type": role,
                "sessionId": plan.source.session_id,
                "uuid": f"mem0-handoff-{index}",
                "cwd": cwd,
                "isSidechain": False,
                "message": {"role": role, "content": text},
            }
        )
    if not saw_user:
        raise HandoffError("The active Claude context contains no user message.")
    return records


def _native_import_path(plan: HandoffPlan, claude_projects_dir: Path) -> Path:
    source_key = hashlib.sha256(plan.source.path.encode("utf-8")).hexdigest()[:24]
    safe_session = re.sub(r"[^A-Za-z0-9._-]+", "-", plan.source.session_id).strip("-")
    safe_session = safe_session[:80] or source_key
    return claude_projects_dir.expanduser().resolve() / ".mem0-handoffs" / f"{safe_session}-{source_key}.jsonl"


def _write_native_import(plan: HandoffPlan, path: Path, asset_dir: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    body = "".join(
        json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        for record in _native_import_records(plan, asset_dir)
    )
    _write_private(path, body)
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _native_import_params(source_path: Path, cwd: str) -> dict[str, Any]:
    return {
        "migrationItems": [
            {
                "itemType": "SESSIONS",
                "description": f"Transfer Claude session {source_path.name}",
                "cwd": None,
                "details": {
                    "plugins": [],
                    "sessions": [{"path": str(source_path), "cwd": cwd, "title": None}],
                    "mcpServers": [],
                    "hooks": [],
                    "subagents": [],
                    "commands": [],
                },
            }
        ]
    }


def _thread_id_from_completion(params: Any, source_path: Path) -> str | None:
    if not isinstance(params, dict):
        return None
    canonical = str(source_path.resolve())
    for result in params.get("itemTypeResults") or []:
        if not isinstance(result, dict) or result.get("itemType") != "SESSIONS":
            continue
        for success in result.get("successes") or []:
            if not isinstance(success, dict):
                continue
            if success.get("source") in {None, canonical} and success.get("target"):
                return str(success["target"])
    return None


def _thread_id_from_ledger(codex_home: Path, source_path: Path, content_sha256: str) -> str | None:
    ledger_path = codex_home.expanduser() / "external_agent_session_imports.json"
    if not ledger_path.is_file():
        return None
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    canonical = str(source_path.resolve())
    matches = [
        record
        for record in ledger.get("records", [])
        if isinstance(record, dict)
        and record.get("source_path") == canonical
        and record.get("content_sha256") == content_sha256
        and record.get("imported_thread_id")
    ]
    return str(matches[-1]["imported_thread_id"]) if matches else None


def _notification_thread_id(params: Any) -> str | None:
    if not isinstance(params, dict):
        return None
    if params.get("threadId"):
        return str(params["threadId"])
    turn = params.get("turn")
    if isinstance(turn, dict) and turn.get("threadId"):
        return str(turn["threadId"])
    return None


def _compact_imported_thread(
    server: CodexAppServer,
    thread_id: str,
) -> dict[str, Any] | None:
    server.request("thread/resume", {"threadId": thread_id}, timeout=120)
    server.request("thread/compact/start", {"threadId": thread_id}, timeout=30)

    latest_usage: dict[str, Any] | None = None
    saw_compaction_item = False
    while True:
        notification = server.wait_for_any_notification(
            {"item/completed", "thread/tokenUsage/updated", "turn/completed", "error"},
            lambda params: _notification_thread_id(params) in {None, thread_id},
            timeout=600,
        )
        method = notification.get("method")
        params = notification.get("params")
        if method == "thread/tokenUsage/updated" and isinstance(params, dict):
            token_usage = params.get("tokenUsage")
            if isinstance(token_usage, dict):
                latest_usage = token_usage
            continue
        if method == "item/completed" and isinstance(params, dict):
            item = params.get("item")
            if isinstance(item, dict) and item.get("type") == "contextCompaction":
                saw_compaction_item = True
            continue
        if method == "error":
            error = params.get("error") if isinstance(params, dict) else params
            raise HandoffError(f"Codex could not compact the imported task: {error}")
        if method == "turn/completed" and isinstance(params, dict):
            turn = params.get("turn")
            if not isinstance(turn, dict):
                raise HandoffError("Codex returned an invalid compaction result.")
            if turn.get("status") != "completed":
                error = turn.get("error") or turn.get("status")
                raise HandoffError(f"Codex could not compact the imported task: {error}")
            if not saw_compaction_item:
                raise HandoffError("Codex completed the compaction turn without a compaction item.")
            return latest_usage


def _set_thread_name(
    server: CodexAppServer,
    thread_id: str,
    name: str,
) -> None:
    server.request(
        "thread/name/set",
        {"threadId": thread_id, "name": name},
        timeout=30,
    )


def create_codex_thread(
    plan: HandoffPlan,
    codex_bin: str = "codex",
    codex_home: Path = DEFAULT_CODEX_HOME,
) -> dict[str, Any]:
    limits = _codex_context_limits(codex_home)
    should_compact = plan.approximate_tokens >= limits.auto_compact_token_limit
    if should_compact and plan.approximate_tokens >= limits.max_auto_compact_token_limit:
        raise HandoffError(
            f"The active session state is approximately {plan.approximate_tokens:,} tokens. "
            f"Codex cannot safely compact more than approximately "
            f"{limits.max_auto_compact_token_limit:,} tokens in one request. "
            "Compact in the source host and retry the handoff."
        )

    # Codex only imports sources staged under its native Claude home.
    source_path = _native_import_path(plan, Path.home() / ".claude" / "projects")
    safe_session = re.sub(r"[^A-Za-z0-9._-]+", "-", plan.source.session_id).strip("-")
    asset_dir = (
        codex_home.expanduser().resolve()
        / "external-agent-assets"
        / plan.source.host
        / (safe_session[:80] or "session")
    )
    content_sha256 = _write_native_import(plan, source_path, asset_dir)
    try:
        context_override = limits.max_context_window if should_compact else None
        with CodexAppServer(codex_bin, context_override, codex_home=codex_home) as server:
            response = server.request(
                "externalAgentConfig/import",
                _native_import_params(source_path, _codex_cwd(plan)),
                timeout=120,
            )
            import_id = str((response or {}).get("importId") or "")
            if not import_id:
                raise HandoffError(f"Codex externalAgentConfig/import returned no import ID: {response!r}")
            completed = server.wait_for_notification(
                IMPORT_COMPLETED_NOTIFICATION,
                lambda params: isinstance(params, dict) and params.get("importId") == import_id,
            )
            completed_params = completed.get("params")
            thread_id = _thread_id_from_completion(completed_params, source_path)
            if not thread_id:
                thread_id = _thread_id_from_ledger(codex_home, source_path, content_sha256)
            if not thread_id:
                raise HandoffError(
                    "Codex finished importing the session but did not report the new task ID. "
                    f"Import result: {json.dumps(completed_params, ensure_ascii=False)}"
                )

            read = server.request(
                "thread/read",
                {"threadId": thread_id, "includeTurns": True},
            )
            thread = (read or {}).get("thread") if isinstance(read, dict) else None
            if not isinstance(thread, dict):
                raise HandoffError(f"Codex could not read imported task {thread_id}.")
            turns = thread.get("turns") or []
            preview = str(thread.get("preview") or "")
            if not turns or not preview:
                raise HandoffError(f"Codex imported task {thread_id}, but it has no visible history.")

            compaction_usage = _compact_imported_thread(server, thread_id) if should_compact else None
            _set_thread_name(server, thread_id, plan.source.title)

            return {
                "thread_id": thread_id,
                "title": plan.source.title,
                "cwd": _codex_cwd(plan),
                "source_session_id": plan.source.session_id,
                "source_host": plan.source.host,
                "visible_turns": len(turns),
                "preview": preview,
                "responses_items_converted": len(plan.items),
                "approximate_import_tokens": plan.approximate_tokens,
                "target_model": limits.model,
                "target_context_window": limits.context_window,
                "target_usable_context_window": limits.usable_context_window,
                "target_auto_compact_token_limit": limits.auto_compact_token_limit,
                "compacted_before_return": should_compact,
                "compaction_context_window": (limits.max_context_window if should_compact else None),
                "compaction_token_usage": compaction_usage,
                "model_invoked": should_compact,
            }
    finally:
        source_path.unlink(missing_ok=True)
        try:
            source_path.parent.rmdir()
        except OSError:
            pass


def _summary(plan: HandoffPlan) -> dict[str, Any]:
    return {
        "source": plan.source.path,
        "source_host": plan.source.host,
        "session_id": plan.source.session_id,
        "title": plan.source.title,
        "source_cwd": plan.source.cwd,
        "codex_cwd": _codex_cwd(plan),
        "leaf_uuid": plan.source.leaf_uuid,
        "compact_boundary_uuid": plan.source.compact_boundary_uuid,
        "source_records": plan.source_records,
        "active_records": plan.active_records,
        "imported_records": plan.imported_records,
        "responses_items": len(plan.items),
        "approximate_import_tokens": plan.approximate_tokens,
        "warnings": plan.warnings,
    }


def _command_output(result: dict[str, Any]) -> str:
    title = str(result["title"])
    cwd = str(result["cwd"])
    project = Path(cwd).name or cwd
    lines = [
        f'Created Codex task "{title}".',
        f"Task ID: {result['thread_id']}",
        f"Project: {project}",
    ]
    if result.get("compacted_before_return"):
        lines.append("Codex compacted the transferred context before opening the task.")
    lines.append(f'Open Codex and select "{title}" under {project}.')
    return "\n".join(lines)


def _parse_args(argv: Iterable[str] | None = None, default_source: str | None = "claude-code") -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--session", help="Native session transcript path (Claude also accepts its session ID)")
    parser.add_argument(
        "--source",
        choices=("claude-code", "cursor", "codex", "kimi", "antigravity", "openclaw", "pi-agent"),
        default=default_source,
    )
    parser.add_argument("--title", help="Override the imported task title")
    source.add_argument("--bundle", type=Path, help="Previously exported handoff bundle")
    parser.add_argument(
        "--claude-projects-dir",
        type=Path,
        default=Path.home() / ".claude" / "projects",
    )
    parser.add_argument("--export", type=Path, help="Write a private reusable handoff bundle")
    parser.add_argument(
        "--cwd",
        type=Path,
        help="Use this existing directory instead of the source session's directory",
    )
    parser.add_argument("--create", action="store_true", help="Create the Codex task")
    parser.add_argument(
        "--target",
        choices=("codex",),
        default="codex",
        help="Destination coding agent",
    )
    parser.add_argument(
        "--command-output",
        action="store_true",
        help="Print the short result used by Mem0's user-facing command",
    )
    parser.add_argument("--codex-bin", default="codex")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=DEFAULT_CODEX_HOME,
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None, default_source: str | None = "claude-code") -> int:
    args = _parse_args(argv, default_source)
    try:
        if args.bundle:
            plan = load_bundle(args.bundle)
        elif args.source == "claude-code":
            plan = build_plan(args.session, args.claude_projects_dir)
        else:
            if not args.source:
                raise HandoffError("--source is required with --session.")
            from handoff_sources import read_source

            plan = read_source(args.source, Path(args.session), cwd=args.cwd, title=args.title)
        if args.title:
            plan = replace(plan, source=replace(plan.source, title=args.title))
        plan = _with_cwd(plan, args.cwd)
        output: dict[str, Any] = {"plan": _summary(plan)}
        if args.export:
            output["bundle"] = str(write_bundle(plan, args.export))
        if args.create:
            try:
                output["codex"] = create_codex_thread(
                    plan,
                    codex_bin=args.codex_bin,
                    codex_home=args.codex_home.expanduser(),
                )
            except (HandoffError, OSError, subprocess.SubprocessError) as exc:
                fallback = args.export or _default_bundle_path(plan)
                saved = write_bundle(plan, fallback)
                raise HandoffError(f"{exc} The complete handoff was saved at {saved}.") from exc
        if args.command_output:
            if not args.create:
                raise HandoffError("--command-output requires --create.")
            print(_command_output(output["codex"]))
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    except (HandoffError, OSError, subprocess.SubprocessError) as exc:
        print(f"handoff failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
