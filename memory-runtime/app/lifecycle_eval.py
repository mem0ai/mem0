from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.services.lifecycle import LifecycleService


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _memory_unit_from_scenario(data: dict[str, Any], *, now: datetime) -> SimpleNamespace:
    return SimpleNamespace(
        freshness_score=data.get("freshness_score", 1.0),
        importance_score=data.get("importance_score", 0.0),
        access_count=data.get("access_count", 0),
        status=data.get("status", "active"),
        created_at=now - timedelta(hours=float(data.get("age_hours", 0.0))),
    )


def run_lifecycle_eval(*, scenarios: list[dict[str, Any]]) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    results: list[dict[str, Any]] = []
    passed = 0
    action_matches = 0
    status_matches = 0
    destructive_actions = 0
    freshness_values: list[float] = []

    for scenario in scenarios:
        memory_unit = _memory_unit_from_scenario(scenario["memory_unit"], now=now)
        decision = LifecycleService.evaluate_transition(
            memory_unit=memory_unit,
            space_type=scenario["space_type"],
            now=now,
        )
        expected = scenario["expected"]
        action_ok = decision.action == expected["action"]
        status_ok = decision.new_status == expected["status"]
        freshness_min = expected.get("freshness_min")
        freshness_max = expected.get("freshness_max")
        freshness_ok = True
        if freshness_min is not None and decision.new_freshness_score < freshness_min:
            freshness_ok = False
        if freshness_max is not None and decision.new_freshness_score > freshness_max:
            freshness_ok = False

        scenario_passed = action_ok and status_ok and freshness_ok
        if scenario_passed:
            passed += 1
        if action_ok:
            action_matches += 1
        if status_ok:
            status_matches += 1
        if decision.action in {"archived", "evicted"}:
            destructive_actions += 1
        freshness_values.append(decision.new_freshness_score)

        results.append(
            {
                "id": scenario["id"],
                "description": scenario["description"],
                "passed": scenario_passed,
                "expected": expected,
                "actual": {
                    "action": decision.action,
                    "status": decision.new_status,
                    "freshness_score": round(decision.new_freshness_score, 4),
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
            "action_match_rate": round((action_matches / total) if total else 1.0, 4),
            "status_match_rate": round((status_matches / total) if total else 1.0, 4),
            "destructive_action_rate": round((destructive_actions / total) if total else 0.0, 4),
            "mean_freshness_score": round((sum(freshness_values) / total) if total else 0.0, 4),
        },
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run lifecycle evaluation scenarios.")
    parser.add_argument(
        "--scenarios",
        default="tests/fixtures/evals/lifecycle_quality_scenarios.json",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.scenarios)
    report = run_lifecycle_eval(scenarios=scenarios)

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
