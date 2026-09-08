#!/usr/bin/env python3
"""Detached remote checkpoint worker.

Claude Code may cancel SessionEnd hooks as a print-mode process exits. The hook
therefore persists its input first and launches this process in a new session.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import telemetry
from memory_core import (
    EvidenceStore,
    checkpoint_session,
    record_stop,
    touch_handoff_heartbeat,
)


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    handoff_path = Path(sys.argv[1])
    os.environ["MEM0_CODE_HANDOFF_PATH"] = str(handoff_path)
    completed = False
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        delay = float(payload.get("delay_seconds") or 0)
        if delay > 0:
            payload.pop("delay_seconds", None)
            handoff_path.write_text(
                json.dumps(payload), encoding="utf-8"
            )
            time.sleep(delay)
            if not handoff_path.exists():
                return 0
        hook_input = payload.get("hook_input") or {}
        reason = str(payload.get("reason") or "checkpoint")
        wait_for_inflight = bool(payload.get("wait_for_inflight"))
        store = EvidenceStore()
        try:
            if wait_for_inflight:
                session_id = str(
                    hook_input.get("session_id") or "unknown-session"
                )
                repo = store.repo_for_session(session_id, hook_input.get("cwd"))
                deadline = time.monotonic() + float(
                    os.environ.get("MEM0_CODE_EXTRACTION_WAIT_SECONDS", "120")
                )
                while (
                    store.has_inflight_flush(repo.identity, session_id)
                    and time.monotonic() < deadline
                ):
                    touch_handoff_heartbeat()
                    time.sleep(0.25)
                if reason == "session-end":
                    record_stop(store, hook_input)
            result = checkpoint_session(store, hook_input, reason)
            print(json.dumps(result, sort_keys=True), flush=True)
            completed = result.get("status") in {
                "semantic-succeeded",
                "explicitly-stored",
                "nothing-to-flush",
            }
        finally:
            store.close()
        return 0
    finally:
        telemetry.flush()
        if completed:
            try:
                handoff_path.unlink()
            except OSError:
                pass
        elif handoff_path.suffix == ".running":
            try:
                handoff_path.replace(handoff_path.with_suffix(".json"))
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
