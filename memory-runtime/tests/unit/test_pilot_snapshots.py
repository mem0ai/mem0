from __future__ import annotations

import json
from datetime import UTC, datetime

from app.pilot_snapshots import (
    build_snapshot_manifest,
    default_snapshot_name,
    sanitize_snapshot_name,
    write_snapshot_manifest,
)


def test_sanitize_snapshot_name_normalizes_symbols() -> None:
    assert sanitize_snapshot_name("  pilot / before live  ") == "pilot-before-live"
    assert sanitize_snapshot_name("!!!") == "snapshot"


def test_default_snapshot_name_uses_timestamp() -> None:
    now = datetime(2026, 4, 20, 3, 45, 1, tzinfo=UTC)
    assert default_snapshot_name(now) == "snapshot-20260420-034501"


def test_build_snapshot_manifest_collects_metadata() -> None:
    created = datetime(2026, 4, 20, 3, 45, 1, tzinfo=UTC)
    manifest = build_snapshot_manifest(
        snapshot_name="pilot-before-live",
        created_at=created,
        report_files=["b.json", "a.json"],
        has_observability_snapshot=True,
    )

    assert manifest["snapshot_name"] == "pilot-before-live"
    assert manifest["created_at"] == created.isoformat()
    assert manifest["reports"] == ["a.json", "b.json"]
    assert manifest["has_observability_snapshot"] is True


def test_write_snapshot_manifest_reads_reports_directory(tmp_path) -> None:
    snapshot_dir = tmp_path / "pilot-before-live"
    reports_dir = snapshot_dir / "reports"
    reports_dir.mkdir(parents=True)
    (reports_dir / "openclaw_pilot_smoke_report.json").write_text("{}", encoding="utf-8")
    (snapshot_dir / "observability_stats.json").write_text("{}", encoding="utf-8")

    manifest_path = write_snapshot_manifest(snapshot_dir, snapshot_name="pilot-before-live")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["snapshot_name"] == "pilot-before-live"
    assert manifest["reports"] == ["openclaw_pilot_smoke_report.json"]
    assert manifest["has_observability_snapshot"] is True
