from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import Engine, text


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def run_adversarial_eval(
    client,
    *,
    engine: Engine,
    namespace_id: str,
    agent_id: str,
    scenarios: list[dict[str, Any]],
    job_drainer: Callable[[], int],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    false_accepts = 0
    false_rejects = 0
    rejected = 0
    accepted = 0

    for scenario in scenarios:
        expected_outcome = scenario["expected"]["outcome"]
        with engine.connect() as connection:
            before_memory_units = connection.execute(text("SELECT COUNT(*) FROM memory_units")).scalar_one()
            before_rejections = connection.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE action = 'memory_candidate_rejected_low_trust'")
            ).scalar_one()

        response = client.post(
            "/v1/events",
            json={
                "namespace_id": namespace_id,
                "agent_id": agent_id,
                "source_system": "openclaw",
                **scenario["event"],
            },
        )
        response.raise_for_status()
        job_drainer()

        with engine.connect() as connection:
            after_memory_units = connection.execute(text("SELECT COUNT(*) FROM memory_units")).scalar_one()
            after_rejections = connection.execute(
                text("SELECT COUNT(*) FROM audit_log WHERE action = 'memory_candidate_rejected_low_trust'")
            ).scalar_one()
            audit_row = connection.execute(
                text(
                    "SELECT action, details_json FROM audit_log ORDER BY created_at DESC LIMIT 1"
                )
            ).fetchone()

        created_delta = after_memory_units - before_memory_units
        rejection_delta = after_rejections - before_rejections
        actual_outcome = "rejected" if rejection_delta > 0 else "accepted"
        if actual_outcome == "rejected":
            rejected += 1
        else:
            accepted += 1

        expected_reason = scenario["expected"].get("reason")
        actual_reason = None
        if audit_row is not None and audit_row[0] == "memory_candidate_rejected_low_trust":
            details = audit_row[1]
            if isinstance(details, str):
                try:
                    details = json.loads(details)
                except json.JSONDecodeError:
                    details = {}
            actual_reason = (details or {}).get("reason")

        scenario_passed = actual_outcome == expected_outcome and (
            expected_reason is None or actual_reason == expected_reason
        )
        if scenario_passed:
            passed += 1
        elif expected_outcome == "rejected":
            false_accepts += 1
        else:
            false_rejects += 1

        results.append(
            {
                "id": scenario["id"],
                "description": scenario["description"],
                "passed": scenario_passed,
                "expected": scenario["expected"],
                "actual": {
                    "outcome": actual_outcome,
                    "reason": actual_reason,
                    "memory_units_created_delta": created_delta,
                    "rejections_delta": rejection_delta,
                },
            }
        )

    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 1.0, 4),
        "metrics": {
            "rejection_rate": round((rejected / total) if total else 0.0, 4),
            "acceptance_rate": round((accepted / total) if total else 0.0, 4),
            "false_accepts": false_accepts,
            "false_rejects": false_rejects,
        },
        "results": results,
    }
