from __future__ import annotations

import argparse
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORT_FILENAMES = (
    "openclaw_preflight_report.json",
    "openclaw_pilot_smoke_report.json",
    "openclaw_pilot_scenarios_report.json",
    "recall_quality_eval_report.json",
)


def sanitize_snapshot_name(raw_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name.strip())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-._")
    return sanitized or "snapshot"


def default_snapshot_name(now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"snapshot-{timestamp}"


def build_snapshot_manifest(
    *,
    snapshot_name: str,
    created_at: datetime | None = None,
    sql_dump_name: str = "memory_runtime.sql",
    report_files: list[str] | None = None,
    has_observability_snapshot: bool = False,
) -> dict[str, Any]:
    created = (created_at or datetime.now(UTC)).isoformat()
    reports = sorted(report_files or [])
    return {
        "snapshot_name": snapshot_name,
        "created_at": created,
        "sql_dump": sql_dump_name,
        "reports": reports,
        "has_observability_snapshot": has_observability_snapshot,
    }


def write_snapshot_manifest(
    snapshot_dir: str | Path,
    *,
    snapshot_name: str,
    created_at: datetime | None = None,
) -> Path:
    directory = Path(snapshot_dir)
    reports_dir = directory / "reports"
    report_files = []
    if reports_dir.exists():
        report_files = [path.name for path in reports_dir.iterdir() if path.is_file()]

    manifest = build_snapshot_manifest(
        snapshot_name=snapshot_name,
        created_at=created_at,
        report_files=report_files,
        has_observability_snapshot=(directory / "observability_stats.json").exists(),
    )
    path = directory / "manifest.json"
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Pilot snapshot helper utilities.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--default-name", action="store_true")
    group.add_argument("--sanitize")
    group.add_argument("--write-manifest", action="store_true")
    parser.add_argument("--snapshot-dir")
    parser.add_argument("--name")
    args = parser.parse_args(argv)

    if args.default_name:
        print(default_snapshot_name())
        return 0

    if args.sanitize is not None:
        print(sanitize_snapshot_name(args.sanitize))
        return 0

    if not args.snapshot_dir or not args.name:
        parser.error("--snapshot-dir and --name are required with --write-manifest")

    path = write_snapshot_manifest(
        args.snapshot_dir,
        snapshot_name=sanitize_snapshot_name(args.name),
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
