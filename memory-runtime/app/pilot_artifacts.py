from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ARTIFACT_ROOT = Path(__file__).resolve().parent.parent / ".artifacts" / "pilot_traces"


def sanitize_artifact_name(raw_name: str) -> str:
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", raw_name.strip())
    sanitized = re.sub(r"-{2,}", "-", sanitized).strip("-._")
    return sanitized or "run"


def default_artifact_run_name(prefix: str, now: datetime | None = None) -> str:
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%d-%H%M%S")
    return f"{sanitize_artifact_name(prefix)}-{timestamp}"


def export_trace_bundle(
    *,
    category: str,
    run_name: str,
    payloads: dict[str, Any],
) -> Path:
    target_dir = ARTIFACT_ROOT / sanitize_artifact_name(category) / sanitize_artifact_name(run_name)
    target_dir.mkdir(parents=True, exist_ok=True)

    for name, payload in payloads.items():
        filename = f"{sanitize_artifact_name(name)}.json"
        (target_dir / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    manifest = {
        "category": sanitize_artifact_name(category),
        "run_name": sanitize_artifact_name(run_name),
        "created_at": datetime.now(UTC).isoformat(),
        "files": sorted(f"{sanitize_artifact_name(name)}.json" for name in payloads),
    }
    (target_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target_dir
