from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import httpx


def load_scenarios(path: str | Path) -> list[dict[str, Any]]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _flatten_brief(brief: dict[str, list[str]]) -> str:
    return "\n".join(item for items in brief.values() for item in items)


def run_quality_eval(
    client,
    *,
    scenarios: list[dict[str, Any]],
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    passed = 0
    required_total = 0
    required_hits = 0
    forbidden_total = 0
    forbidden_leaks = 0
    total_selected = 0
    scenario_scores: list[float] = []

    for scenario in scenarios:
        response = client.post("/v1/recall", json=scenario["request"])
        response.raise_for_status()
        payload = response.json()
        flattened = _flatten_brief(payload["brief"])

        required = scenario.get("must_contain", [])
        forbidden = scenario.get("must_not_contain", [])
        missing = [text for text in required if text not in flattened]
        unexpected = [text for text in forbidden if text in flattened]
        ok = not missing and not unexpected
        if ok:
            passed += 1
        scenario_required_hits = len(required) - len(missing)
        scenario_forbidden_leaks = len(unexpected)
        required_total += len(required)
        required_hits += scenario_required_hits
        forbidden_total += len(forbidden)
        forbidden_leaks += scenario_forbidden_leaks
        selected_count = payload["trace"]["selected_count"]
        total_selected += selected_count
        required_hit_rate = (scenario_required_hits / len(required)) if required else 1.0
        forbidden_leak_rate = (scenario_forbidden_leaks / len(forbidden)) if forbidden else 0.0
        scenario_score = round((required_hit_rate + (1.0 - forbidden_leak_rate)) / 2.0, 4)
        scenario_scores.append(scenario_score)

        results.append(
            {
                "id": scenario["id"],
                "description": scenario["description"],
                "passed": ok,
                "missing": missing,
                "unexpected": unexpected,
                "required_total": len(required),
                "required_hits": scenario_required_hits,
                "required_hit_rate": round(required_hit_rate, 4),
                "forbidden_total": len(forbidden),
                "forbidden_leaks": scenario_forbidden_leaks,
                "forbidden_leak_rate": round(forbidden_leak_rate, 4),
                "selected_count": selected_count,
                "scenario_score": scenario_score,
                "trace": payload["trace"],
            }
        )

    total = len(results)
    metrics = {
        "required_total": required_total,
        "required_hits": required_hits,
        "required_hit_rate": round((required_hits / required_total) if required_total else 1.0, 4),
        "forbidden_total": forbidden_total,
        "forbidden_leaks": forbidden_leaks,
        "forbidden_leak_rate": round((forbidden_leaks / forbidden_total) if forbidden_total else 0.0, 4),
        "avg_selected_count": round((total_selected / total) if total else 0.0, 4),
        "mean_scenario_score": round((sum(scenario_scores) / total) if total else 1.0, 4),
    }
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 1.0, 4),
        "metrics": metrics,
        "results": results,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run recall quality evaluation scenarios.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument(
        "--scenarios",
        default="tests/fixtures/evals/recall_quality_scenarios.json",
    )
    args = parser.parse_args(argv)

    scenarios = load_scenarios(args.scenarios)
    with httpx.Client(base_url=args.base_url, timeout=10.0) as client:
        report = run_quality_eval(client, scenarios=scenarios)

    print(json.dumps(report, ensure_ascii=False))
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
