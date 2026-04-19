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

    for scenario in scenarios:
        response = client.post("/v1/recall", json=scenario["request"])
        response.raise_for_status()
        payload = response.json()
        flattened = _flatten_brief(payload["brief"])

        missing = [text for text in scenario.get("must_contain", []) if text not in flattened]
        unexpected = [text for text in scenario.get("must_not_contain", []) if text in flattened]
        ok = not missing and not unexpected
        if ok:
            passed += 1

        results.append(
            {
                "id": scenario["id"],
                "description": scenario["description"],
                "passed": ok,
                "missing": missing,
                "unexpected": unexpected,
                "trace": payload["trace"],
            }
        )

    total = len(results)
    return {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round((passed / total) if total else 1.0, 4),
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
