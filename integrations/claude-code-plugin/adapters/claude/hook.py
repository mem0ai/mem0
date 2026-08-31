#!/usr/bin/env python3
"""Claude Code hooks for Mem0."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "core"))

import telemetry
from memory_core import (
    EvidenceStore,
    api_key,
    cache_plugin_api_key,
    checkpoint_session,
    clear_stale_api_key_cache,
    data_dir,
    detached_process_kwargs,
    format_context,
    record_session_start,
    record_sidekick_start,
    record_sidekick_stop,
    record_stop,
    record_tool,
    record_user_prompt,
    search_memories,
)


STALE_RUNNING_SECONDS = 300
PENDING_EXPIRY_SECONDS = 7 * 24 * 60 * 60
PENDING_LAUNCH_LIMIT = 5


def read_hook_input() -> dict:
    try:
        value = json.load(sys.stdin)
        return value if isinstance(value, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def first_prompt_memory_output(store: EvidenceStore, hook_input: dict) -> dict:
    """Search once before Claude handles the first prompt in a session."""
    repo, session_id, prompt, is_first_prompt = record_user_prompt(store, hook_input)
    if not is_first_prompt:
        return {}
    try:
        minimum_query_chars = int(os.environ.get("MEM0_CODE_MIN_QUERY_CHARS", "20"))
    except ValueError:
        minimum_query_chars = 20
    if len(prompt.strip()) < max(minimum_query_chars, 1):
        return {}
    result = search_memories(
        store,
        repo,
        session_id,
        prompt,
        top_k=5,
        operation="first-prompt-search",
        timeout=2,
    )
    if not result.memories:
        return {}
    context = format_context(
        result.memories,
        "Mem0 found these relevant memories from earlier work in this repository:",
    )
    telemetry.record(
        "context_injected",
        repo=repo,
        session_id=session_id,
        trigger="first-prompt",
        memory_count=len(result.memories),
        context_chars=len(context),
        prompt_chars=len(prompt),
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": context,
        },
    }


def _launch_handoff(handoff_path: Path) -> bool:
    running_path = handoff_path.with_suffix(".running")
    try:
        handoff_path.replace(running_path)
    except OSError:
        return False
    worker = Path(__file__).resolve().parents[2] / "core" / "flush_worker.py"
    log_path = data_dir() / "flush-worker.log"
    log_handle = open(log_path, "a", encoding="utf-8")
    try:
        subprocess.Popen(
            [sys.executable, str(worker), str(running_path)],
            stdin=subprocess.DEVNULL,
            stdout=log_handle,
            stderr=log_handle,
            close_fds=True,
            **detached_process_kwargs(),
        )
    finally:
        log_handle.close()
    return True


def recover_pending_handoffs() -> int:
    pending_dir = data_dir() / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    now = time.time()
    for running in pending_dir.glob("*.running"):
        try:
            if now - running.stat().st_mtime > STALE_RUNNING_SECONDS:
                running.replace(running.with_suffix(".json"))
        except OSError:
            continue
    recoverable = []
    for handoff in pending_dir.glob("*.json"):
        try:
            age = now - handoff.stat().st_mtime
        except OSError:
            continue
        if age > PENDING_EXPIRY_SECONDS:
            handoff.unlink(missing_ok=True)
            continue
        recoverable.append((age, handoff))
    recoverable.sort(key=lambda item: item[0], reverse=True)
    launched = 0
    for _, handoff in recoverable[:PENDING_LAUNCH_LIMIT]:
        launched += int(_launch_handoff(handoff))
    return launched


def refresh_pending_handoffs() -> None:
    """Hold unsent packets while paused instead of letting them expire."""
    pending_dir = data_dir() / "pending"
    if not pending_dir.is_dir():
        return
    for pattern in ("*.json", "*.running"):
        for handoff in pending_dir.glob(pattern):
            try:
                os.utime(handoff)
            except OSError:
                continue


def hand_off_flush(
    hook_input: dict, reason: str, *, wait_for_inflight: bool = False
) -> None:
    """Persist hook input and detach delivery from Claude's shutdown lifecycle."""
    pending_dir = data_dir() / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    material = (
        f"{hook_input.get('cwd', '')}\0{hook_input.get('session_id', '')}\0{reason}"
    )
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    handoff_path = pending_dir / f"{digest}-{uuid.uuid4().hex[:8]}.json"
    temporary_path = handoff_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps(
            {
                "hook_input": hook_input,
                "reason": reason,
                "wait_for_inflight": wait_for_inflight,
            }
        ),
        encoding="utf-8",
    )
    temporary_path.replace(handoff_path)
    _launch_handoff(handoff_path)


def automatic_flush_enabled() -> bool:
    return os.environ.get("MEM0_CODE_AUTO_FLUSH", "true").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def schedule_periodic_checkpoint(
    store: EvidenceStore,
    hook_input: dict,
    repo,
    session_id: str,
) -> bool:
    """Start one background extraction when a complete block is ready."""
    if (
        not automatic_flush_enabled()
        or not api_key()
        or not store.checkpoint_due(repo.identity, session_id)
    ):
        return False
    if store.prepare_flush(repo, session_id, "periodic") is None:
        return False
    hand_off_flush(hook_input, "periodic")
    return True


DEFAULT_IDLE_FLUSH_SECONDS = 300


def _idle_flush_seconds() -> int:
    try:
        return max(
            int(os.environ.get("MEM0_CODE_IDLE_FLUSH_SECONDS", str(DEFAULT_IDLE_FLUSH_SECONDS))),
            0,
        )
    except ValueError:
        return DEFAULT_IDLE_FLUSH_SECONDS


def schedule_idle_flush(
    store: EvidenceStore,
    hook_input: dict,
    repo,
    session_id: str,
) -> bool:
    """Launch a delayed background flush for sessions that may never end."""
    delay = _idle_flush_seconds()
    if delay <= 0 or not automatic_flush_enabled() or not api_key():
        return False
    if store.has_inflight_flush(repo.identity, session_id):
        return False
    if not store.has_unflushed_events(repo.identity, session_id):
        return False
    pending_dir = data_dir() / "pending"
    pending_dir.mkdir(parents=True, exist_ok=True)
    material = f"idle\0{hook_input.get('cwd', '')}\0{hook_input.get('session_id', '')}"
    digest = hashlib.sha256(material.encode()).hexdigest()[:24]
    for old in pending_dir.glob(f"idle-{digest}*"):
        old.unlink(missing_ok=True)
    handoff_path = pending_dir / f"idle-{digest}-{uuid.uuid4().hex[:8]}.json"
    temporary_path = handoff_path.with_suffix(".tmp")
    temporary_path.write_text(
        json.dumps({
            "hook_input": hook_input,
            "reason": "idle",
            "delay_seconds": delay,
        }),
        encoding="utf-8",
    )
    temporary_path.replace(handoff_path)
    _launch_handoff(handoff_path)
    return True


def log_failure(exc: Exception) -> None:
    try:
        log_path = data_dir() / "plugin-errors.log"
        with log_path.open("a", encoding="utf-8") as handle:
            handle.write(f"{time.time():.3f} {type(exc).__name__}: {exc}\n")
    except OSError:
        pass


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action",
        choices=[
            "session-start",
            "user-prompt",
            "post-tool",
            "post-tool-failure",
            "sidekick-start",
            "sidekick-stop",
            "stop",
            "flush",
        ],
    )
    parser.add_argument("--reason", default="manual")
    parser.add_argument("--plugin-data-dir", default="")
    args = parser.parse_args()
    if args.plugin_data_dir:
        os.environ["MEM0_CODE_DATA_DIR"] = args.plugin_data_dir
    cache_plugin_api_key()
    if args.action == "session-start":
        clear_stale_api_key_cache()
    hook_input = read_hook_input()
    store = EvidenceStore()
    try:
        if store.is_paused():
            if args.action == "session-start":
                refresh_pending_handoffs()
                telemetry.record("session_start", paused=True)
                telemetry.spawn_flush()
            return 0
        if args.action == "session-start":
            if telemetry.is_first_run():
                telemetry.record("install")
            recovered = recover_pending_handoffs()
            record_session_start(store, hook_input)
            if recovered:
                telemetry.record("handoff_recovered", count=recovered)
            telemetry.spawn_flush()
        elif args.action == "user-prompt":
            output = first_prompt_memory_output(store, hook_input)
            if output:
                print(json.dumps(output))
        elif args.action == "post-tool":
            record_tool(store, hook_input)
        elif args.action == "post-tool-failure":
            record_tool(store, hook_input, failed=True)
        elif args.action == "sidekick-start":
            context = record_sidekick_start(store, hook_input)
            if context:
                print(
                    json.dumps(
                        {
                            "hookSpecificOutput": {
                                "hookEventName": "SubagentStart",
                                "additionalContext": context,
                            }
                        }
                    )
                )
        elif args.action == "sidekick-stop":
            record_sidekick_stop(store, hook_input)
        elif args.action == "stop":
            repo, session_id = record_stop(store, hook_input)
            if not schedule_periodic_checkpoint(store, hook_input, repo, session_id):
                schedule_idle_flush(store, hook_input, repo, session_id)
        elif args.action == "flush":
            automatic = args.reason in {"session-end", "pre-compact"}
            if automatic and not automatic_flush_enabled():
                return 0
            if args.reason == "session-end":
                # In print mode, SessionEnd can arrive before the Stop hook has
                # recorded Claude's final response. Read any remaining visible
                # transcript messages before preparing the final extraction.
                record_stop(store, hook_input)
            if os.environ.get("MEM0_CODE_SYNC_FLUSH") == "1":
                print(json.dumps(checkpoint_session(store, hook_input, args.reason)))
            else:
                session_id = str(hook_input.get("session_id") or "unknown-session")
                repo = store.repo_for_session(session_id, hook_input.get("cwd"))
                already_running = store.has_inflight_flush(repo.identity, session_id)
                if already_running and args.reason == "session-end":
                    hand_off_flush(
                        hook_input, args.reason, wait_for_inflight=True
                    )
                elif not already_running and store.prepare_flush(
                    repo, session_id, args.reason
                ) is not None:
                    hand_off_flush(hook_input, args.reason)
    finally:
        store.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Memory must never prevent the coding agent from continuing.
        log_failure(exc)
        raise SystemExit(0)
