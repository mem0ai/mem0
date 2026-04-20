from __future__ import annotations

import json
from datetime import UTC, datetime

from app.pilot_artifacts import default_artifact_run_name, export_trace_bundle, sanitize_artifact_name


def test_sanitize_artifact_name_removes_unsafe_symbols() -> None:
    assert sanitize_artifact_name("  live pilot / smoke  ") == "live-pilot-smoke"
    assert sanitize_artifact_name("___") == "run"


def test_default_artifact_run_name_adds_timestamp() -> None:
    now = datetime(2026, 4, 20, 4, 0, 0, tzinfo=UTC)
    assert default_artifact_run_name("pilot-smoke", now) == "pilot-smoke-20260420-040000"


def test_export_trace_bundle_writes_files_and_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr("app.pilot_artifacts.ARTIFACT_ROOT", tmp_path)

    target_dir = export_trace_bundle(
        category="pilot-smoke",
        run_name="before-live",
        payloads={
            "recall_trace": {"selected": [1, 2]},
            "observability_stats": {"jobs": {"completed": 2}},
        },
    )

    assert (target_dir / "recall_trace.json").exists()
    assert (target_dir / "observability_stats.json").exists()

    manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["category"] == "pilot-smoke"
    assert manifest["run_name"] == "before-live"
    assert manifest["files"] == ["observability_stats.json", "recall_trace.json"]
