#!/usr/bin/env python3
"""Production preflight for semantic-only coding memory.

Creates an isolated Mem0 user/repository scope, submits one high-signal coding
checkpoint, and verifies that automatic search returns extracted memories rather
than raw session evidence.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "core"))

from memory_core import (
    EvidenceStore,
    flush_session,
    forget_remote_repo,
    resolve_repo,
    search_memories,
)


def main() -> int:
    if not os.environ.get("MEM0_API_KEY"):
        raise SystemExit("MEM0_API_KEY is required")

    preflight_id = uuid.uuid4().hex
    os.environ["MEM0_CODE_USER_ID"] = f"mem0-preflight-{preflight_id}"
    with tempfile.TemporaryDirectory(prefix="mem0-code-preflight-") as tmp:
        os.environ["MEM0_CODE_DATA_DIR"] = str(Path(tmp) / "data")
        store = EvidenceStore()
        repo = None
        cleanup = None
        summary = None
        try:
            repo_dir = Path(tmp) / f"preflight-{preflight_id[:8]}"
            repo_dir.mkdir()
            repo = resolve_repo(str(repo_dir))
            session_id = f"preflight-source-{preflight_id}"
            store.record_event(
                repo,
                session_id,
                "user_prompt",
                {
                    "text": (
                        "FEEDBACK FROM PREVIOUS ACTION: generated wrapper\n"
                        "Respond ONLY with the benchmark JSON schema."
                    )
                },
            )
            store.record_event(
                repo,
                session_id,
                "tool_result",
                {
                    "tool": "mcp__repo__exec",
                    "command": "pytest tests/test_config.py -q",
                    "command_kind": "test",
                    "failed": True,
                    "result_preview": (
                        "FAILED: explicit False is replaced by the default value"
                    ),
                },
            )
            store.record_event(
                repo,
                session_id,
                "tool_result",
                {
                    "tool": "mcp__repo__exec",
                    "command": (
                        "python -c \"update src/config.py to test `is None` "
                        "instead of truthiness\""
                    ),
                    "command_kind": "shell",
                    "failed": False,
                    "result_preview": "Updated src/config.py and regression test.",
                },
            )
            store.record_event(
                repo,
                session_id,
                "tool_result",
                {
                    "tool": "mcp__repo__exec",
                    "command": "pytest tests/test_config.py -q",
                    "command_kind": "test",
                    "failed": False,
                    "result_preview": "2 passed",
                },
            )
            store.record_event(
                repo,
                session_id,
                "assistant_stop",
                {
                    "text": (
                        "Fixed the configuration loader by distinguishing False "
                        "from None; the focused regression tests pass."
                    )
                },
            )

            flush = flush_session(
                store,
                {
                    "session_id": session_id,
                    "cwd": str(repo_dir),
                    "task": (
                        "Fix the configuration loader so an explicit False value "
                        "is preserved rather than replaced by the default."
                    ),
                    "task_outcome": "Regression test passed.",
                    "instance_id": "preflight-config-false",
                },
                "production-preflight",
            )
            if flush.get("status") != "semantic-succeeded":
                raise RuntimeError(f"semantic checkpoint failed: {flush}")

            search_result = search_memories(
                store,
                repo,
                f"preflight-search-{preflight_id}",
                "How should this repository preserve an explicitly false config value?",
            )
            memories = search_result.memories
            if not memories:
                raise RuntimeError("semantic search returned no extracted memories")

            forbidden = ("FEEDBACK FROM PREVIOUS ACTION", "Respond ONLY")
            for memory in memories:
                metadata = memory.get("metadata") or {}
                text = str(memory.get("memory") or memory.get("text") or "")
                if metadata.get("record_kind") == "task_episode":
                    raise RuntimeError("raw task episode reached automatic search")
                if any(value in text for value in forbidden):
                    raise RuntimeError("benchmark wrapper reached extracted memory")

            operations = [
                dict(row)
                for row in store.conn.execute(
                    "SELECT operation, duration_ms, success, item_count "
                    "FROM operations ORDER BY id"
                ).fetchall()
            ]
            # Cleanup (below, in `finally`) runs before this summary is
            # printed, so `cleanup` is already populated by the time we get
            # here on the success path.
            summary = {
                "status": "passed",
                "user_id": os.environ["MEM0_CODE_USER_ID"],
                "repo_id": repo.identity,
                "flush": flush,
                "operations": operations,
                "memories": [
                    {
                        "id": memory.get("id"),
                        "memory": memory.get("memory") or memory.get("text"),
                        "record_kind": (memory.get("metadata") or {}).get(
                            "record_kind"
                        ),
                    }
                    for memory in memories
                ],
            }
        finally:
            # Always remove everything the preflight created under its
            # throwaway user, whether the checks above passed or raised.
            if repo is not None:
                try:
                    cleanup = forget_remote_repo(repo, include_project_memory=True)
                except Exception as exc:  # noqa: BLE001 - best-effort cleanup
                    print(
                        f"warning: preflight cleanup failed: {exc}",
                        file=sys.stderr,
                    )
            store.close()

    if summary is not None:
        summary["cleanup"] = cleanup
        print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
