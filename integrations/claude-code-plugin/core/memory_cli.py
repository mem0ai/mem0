#!/usr/bin/env python3
"""Mem0 diagnostics and user controls."""

from __future__ import annotations

import argparse
import json
import os

import telemetry
from memory_core import (
    EvidenceStore,
    api_key,
    data_dir,
    doctor,
    forget_remote_repo,
    resolve_repo,
    user_id,
)


def _print_status(value: dict) -> None:
    last = value.get("last_operation") or {}
    print(f"Mem0: {'paused' if value['paused'] else 'active'}")
    print(f"Repository: {value['repo_id']}")
    print(f"Local data: {value['data_dir']}")
    print(f"API key: {'configured' if value['api_key_configured'] else 'missing'}")
    print(
        "Saved on this computer: "
        f"{value['events']} session details, {value['flushes']} memory updates"
    )
    print(
        f"Used in this repository: {value['retrievals']} memories returned, "
        f"{value['sidekick_runs']} sidekick runs"
    )
    if last:
        item_label = ""
        if last["operation"] in {"flush", "flush-retry"}:
            item_label = f", {last['item_count']} memories"
        operation = (
            "memory update"
            if last["operation"] in {"flush", "flush-retry"}
            else last["operation"].replace("-", " ")
        )
        print(
            f"Last {operation}: "
            f"{'succeeded' if last['success'] else 'failed'} "
            f"({last['duration_ms']:.1f} ms{item_label})"
        )
    sidekick = value.get("last_sidekick") or {}
    if sidekick:
        state = "finished" if sidekick.get("stopped_at") else "started"
        print(
            "Last sidekick: "
            f"{state}, received {sidekick['context_chars']} characters of memory, "
            f"agent {sidekick['agent_id']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-data-dir", default="")
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true")

    doctor_parser = subparsers.add_parser("doctor")
    doctor_parser.add_argument("--json", action="store_true")

    subparsers.add_parser("pause")
    subparsers.add_parser("resume")

    forget = subparsers.add_parser("forget")
    forget.add_argument("--remote", action="store_true")
    forget.add_argument("--yes", action="store_true")
    forget.add_argument("--include-project-memory", action="store_true")

    args = parser.parse_args()
    if args.plugin_data_dir:
        os.environ["MEM0_CODE_DATA_DIR"] = args.plugin_data_dir
    store = EvidenceStore()
    try:
        repo = resolve_repo(os.getcwd())
        telemetry.record("control", repo=repo, action=args.command)
        if args.command == "status":
            result = {
                **store.status(repo.identity),
                "repo_id": repo.identity,
                "app_id": repo.app_id,
                "project_id": repo.project_id,
                "directory": repo.directory,
                "user_id": user_id(),
                "data_dir": str(data_dir()),
                "api_key_configured": bool(api_key()),
            }
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                _print_status(result)
        elif args.command == "doctor":
            result = doctor(os.getcwd())
            if args.json:
                print(json.dumps(result, indent=2, default=str))
            else:
                for name, check in result["checks"].items():
                    print(
                        f"{'PASS' if check['ok'] else 'FAIL'} {name}: {check['detail']}"
                    )
            return 0 if result["ok"] else 1
        elif args.command == "pause":
            store.set_setting("paused", "true")
            print("Mem0 stopped saving and searching memories.")
        elif args.command == "resume":
            store.set_setting("paused", "false")
            print("Mem0 resumed saving and searching memories.")
        elif args.command == "forget":
            if not args.yes:
                print(
                    "Refusing to delete data without --yes. Add --remote to also "
                    "delete this user/repository scope from Mem0."
                )
                return 2
            remote_result = (
                forget_remote_repo(
                    repo, include_project_memory=args.include_project_memory
                )
                if args.remote
                else None
            )
            local_result = store.forget_local_repo(repo.identity)
            print(
                json.dumps(
                    {"local": local_result, "remote": remote_result},
                    indent=2,
                    default=str,
                )
            )
            if remote_result and remote_result.get("status") == "error":
                return 1
    finally:
        store.close()
        telemetry.spawn_flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
